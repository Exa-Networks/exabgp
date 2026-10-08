"""How a session the peer task did not end itself is ended: a timer, a collision, a stop.

Three ways a session ended which the task running it did not choose:

- RFC 4271 8.2.2, OpenConfirm: the hold timer runs there as it does in OpenSent, and its
  expiry sends Hold Timer Expired. No timer ran while we waited for the peer's KEEPALIVE,
  so a peer which sent its OPEN and nothing more held the session for ever.
- RFC 4271 6.8: the connection a collision closes is closed with a Cease, RFC 4486 4's
  Connection Collision Resolution. It was closed without one, and the task running it was
  left going: it then acted on the connection which replaced it.
- RFC 4486 4: a peer removed by a reload is sent Peer De-configured, and every peer is sent
  Administrative Shutdown when the daemon stops. _stop() closed the connection before
  stop() chose the Cease, so neither was ever sent.

The connections are socket pairs: what the peer end reads is what the session wrote.
"""

from __future__ import annotations

import asyncio
import socket
from typing import Any

import pytest

from exabgp.bgp.fsm import FSM, FSMState
from exabgp.bgp.message import KeepAlive, Notify, Open
from exabgp.bgp.message.open import ASN, Capabilities, HoldTime, RouterID, Version
from exabgp.bgp.message.open.capability import ASN4, Capability
from exabgp.bgp.message.open.capability.graceful import Graceful
from exabgp.bgp.timer import ReceiveTimer
from exabgp.environment import getenv
from exabgp.protocol.family import AFI
from exabgp.reactor.network.connection import Connection
from exabgp.reactor.network.incoming import Incoming
from exabgp.reactor.peer import Peer
from exabgp.reactor.protocol import Protocol
from exabgp.rib import RIB
from tests import negotiation

OPEN = 1
NOTIFICATION = 3
KEEPALIVE = 4
HOLD_TIMER_EXPIRED = (4, 0)
ADMINISTRATIVE_SHUTDOWN = (6, 2)
PEER_DE_CONFIGURED = (6, 3)
CONNECTION_COLLISION_RESOLUTION = (6, 7)

# a test waits for the session task this long at most, polling every millisecond
POLL_COUNT = 2000


@pytest.fixture(autouse=True)
def isolated_ribs(monkeypatch: pytest.MonkeyPatch) -> None:
    """A Neighbor takes a RIB out of a process wide cache, so each test gets its own."""
    monkeypatch.setattr(RIB, '_cache', {})


def session_peer(router_id: str = '192.0.2.1') -> Peer:
    configured = negotiation.neighbor(local_as=65001, peer_as=65002, router_id=router_id)
    built, _ = negotiation.peer(configured)
    return built


def connected(peer: Peer) -> tuple[Protocol, socket.socket]:
    proto = Protocol(peer)
    theirs = negotiation.connect(proto)
    peer.proto = proto
    return proto, theirs


def incoming() -> tuple[Incoming, socket.socket]:
    """An accepted connection over a socket pair, and the end the peer holds.

    Incoming() sets TCP options a socket pair refuses, so the connection is built around it.
    """
    ours, theirs = socket.socketpair()
    ours.setblocking(False)
    connection = Incoming.__new__(Incoming)
    Connection.__init__(connection, AFI.ipv4, '192.0.2.2', '192.0.2.1')
    connection.io = ours
    return connection, theirs


def their_open(router_id: str) -> bytes:
    sent = Open.make_open(Version(4), ASN(65002), HoldTime(180), RouterID(router_id), Capabilities())
    return sent.pack_message(negotiation.negotiated())


def notifications(theirs: socket.socket) -> list[tuple[int, int]]:
    return [(body[0], body[1]) for kind, body in negotiation.messages(negotiation.received(theirs)) if kind == 3]


async def until(condition: Any) -> None:
    for _ in range(POLL_COUNT):
        if condition():
            return
        await asyncio.sleep(0.001)
    raise AssertionError('the session never got there')


# ------------------------------------------------------- RFC 4271 8.2.2, the OpenConfirm hold timer


def in_openconfirm(peer: Peer, hold_time: int) -> tuple[Protocol, socket.socket]:
    proto, theirs = connected(peer)
    peer.fsm.change(FSM.OPENCONFIRM)
    proto.negotiated.holdtime = HoldTime(hold_time)
    peer.recv_timer = ReceiveTimer(lambda: 'test', proto.negotiated.holdtime, 4, 0)
    return proto, theirs


@pytest.mark.asyncio
async def test_no_keepalive_within_the_hold_time_is_hold_timer_expired(monkeypatch: pytest.MonkeyPatch) -> None:
    """OpenConfirm: "If the HoldTimer_Expires event (Event 10) occurs before a KEEPALIVE
    message is received, the local system: - sends the NOTIFICATION message with the Error
    Code Hold Timer Expired". The wait is the negotiated hold time, which asyncio is asked for.
    """
    peer = session_peer()
    proto, theirs = in_openconfirm(peer, 90)
    original = asyncio.wait_for
    waited: list[float | None] = []

    async def expired(awaitable: Any, timeout: float | None) -> Any:
        waited.append(timeout)
        awaitable.close()
        raise asyncio.TimeoutError()

    monkeypatch.setattr(asyncio, 'wait_for', expired)
    try:
        with pytest.raises(Notify) as caught:
            await original(peer._read_ka(), timeout=1)
    finally:
        monkeypatch.undo()
        negotiation.disconnect(proto, theirs)

    assert (caught.value.code, caught.value.subcode) == HOLD_TIMER_EXPIRED
    assert waited == [90]


@pytest.mark.asyncio
async def test_a_zero_hold_time_still_does_not_wait_for_ever(monkeypatch: pytest.MonkeyPatch) -> None:
    """A hold time of zero runs no timer: the KEEPALIVE is waited for as long as an OPEN is."""
    peer = session_peer()
    proto, theirs = in_openconfirm(peer, 0)
    # openwait is whole seconds (the compiled build refuses a float): none at all expires at once
    monkeypatch.setattr(getenv().bgp, 'openwait', 0)
    try:
        with pytest.raises(Notify) as caught:
            await asyncio.wait_for(peer._read_ka(), timeout=1)
    finally:
        negotiation.disconnect(proto, theirs)

    assert (caught.value.code, caught.value.subcode) == HOLD_TIMER_EXPIRED


@pytest.mark.asyncio
async def test_a_keepalive_in_time_is_read(monkeypatch: pytest.MonkeyPatch) -> None:
    """The other side: the timer does not fire on a peer which answered."""
    peer = session_peer()
    proto, theirs = in_openconfirm(peer, 90)
    theirs.sendall(KeepAlive.make_keepalive().pack_message(negotiation.negotiated()))
    try:
        await asyncio.wait_for(peer._read_ka(), timeout=1)
    finally:
        negotiation.disconnect(proto, theirs)


# ------------------------------------------------------------- RFC 4271 6.8, connection collision


@pytest.mark.rfc('rfc4271#6.8-collision-closes-one-connection')
@pytest.mark.rfc('rfc4486#4-connection-collision-resolution')
@pytest.mark.asyncio
async def test_the_connection_a_collision_closes_is_sent_a_cease_and_its_task_stops() -> None:
    """The peer's BGP Identifier is the higher, so its connection wins over ours in OpenConfirm.

    Ours is told Connection Collision Resolution, and the task which was running it stops:
    it was left waiting on its KEEPALIVE, and then acted on the incoming connection.
    """
    peer = session_peer(router_id='192.0.2.1')
    proto, theirs = connected(peer)
    theirs.sendall(their_open('192.0.2.2'))
    run = asyncio.create_task(peer._run_session())
    replacement, connecting = incoming()
    try:
        await until(lambda: peer.fsm == FSM.OPENCONFIRM)
        session = peer._session_task
        assert session is not None

        assert peer.handle_connection(replacement) is None
        await until(lambda: session.done())

        assert session.cancelled()
        assert peer.proto is not None and peer.proto.connection is replacement
        sent = negotiation.messages(negotiation.received(theirs))
        assert [kind for kind, _ in sent] == [OPEN, KEEPALIVE, NOTIFICATION]
        assert (sent[-1][1][0], sent[-1][1][1]) == CONNECTION_COLLISION_RESOLUTION
        # nothing reached the connection which replaced it, least of all a Hold Timer Expired
        assert negotiation.received(connecting) == b''
    finally:
        run.cancel()
        await asyncio.gather(run, return_exceptions=True)
        negotiation.disconnect(proto, theirs)
        replacement.close()
        connecting.close()


@pytest.mark.rfc('rfc4271#6.8-collision-closes-one-connection', polarity='negative')
def test_the_connection_from_the_lower_identifier_is_the_one_closed() -> None:
    """Our BGP Identifier is the higher: the new connection is refused, ours goes on untouched."""
    peer = session_peer(router_id='192.0.2.9')
    proto, theirs = connected(peer)
    peer.fsm.change(FSM.OPENCONFIRM)
    proto.negotiated.received_open = Open.make_open(
        Version(4), ASN(65002), HoldTime(180), RouterID('192.0.2.2'), Capabilities()
    )
    replacement, connecting = incoming()
    try:
        refusal = peer.handle_connection(replacement)
        assert refusal is not None
        # bounded: a NOTIFICATION fits in one write to an empty socket buffer
        for _, _ in zip(range(100), refusal):
            pass
        assert notifications(connecting) == [CONNECTION_COLLISION_RESOLUTION]
        assert peer.proto is proto and proto.connection is not None
        assert negotiation.received(theirs) == b''
    finally:
        negotiation.disconnect(proto, theirs)
        connecting.close()


@pytest.mark.rfc('rfc4271#6.8-collision-closes-one-connection')
@pytest.mark.asyncio
async def test_in_opensent_the_incoming_connection_wins_once_its_open_names_a_higher_identifier() -> None:
    """In OpenSent the peer's BGP Identifier is not known until its OPEN arrives.

    Ours was closed as soon as a connection arrived, whatever the identifiers: two speakers
    doing so close both connections. Now nothing is decided before the OPEN of the new
    connection is read, and the session then goes on with that OPEN, not reading another.
    """
    peer = session_peer(router_id='192.0.2.1')
    proto, theirs = connected(peer)
    run = asyncio.create_task(peer._run_session())
    replacement, connecting = incoming()
    taken: asyncio.Task[None] | None = None
    try:
        await until(lambda: peer.fsm == FSM.OPENSENT)
        session = peer._session_task
        assert session is not None

        assert peer.handle_connection(replacement) is None
        for _ in range(10):
            await asyncio.sleep(0.001)
        assert not session.done(), 'nothing is decided before the OPEN of the new connection is read'
        assert peer.proto is proto

        connecting.sendall(their_open('192.0.2.2'))
        await until(lambda: session.done())
        assert session.cancelled()
        assert peer.proto is not None and peer.proto.connection is replacement
        sent = negotiation.messages(negotiation.received(theirs))
        assert [kind for kind, _ in sent] == [OPEN, NOTIFICATION]
        assert (sent[-1][1][0], sent[-1][1][1]) == CONNECTION_COLLISION_RESOLUTION

        # the OPEN already read is the one the session goes on with
        taken = asyncio.create_task(peer._run_session())
        await until(lambda: peer.fsm == FSM.OPENCONFIRM)
        assert [kind for kind, _ in negotiation.messages(negotiation.received(connecting))] == [OPEN, KEEPALIVE]
    finally:
        for task in (run, taken):
            if task is not None:
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
        negotiation.disconnect(proto, theirs)
        replacement.close()
        connecting.close()


@pytest.mark.rfc('rfc4271#6.8-collision-closes-one-connection', polarity='negative')
@pytest.mark.asyncio
async def test_in_opensent_the_incoming_connection_from_a_lower_identifier_is_the_one_closed() -> None:
    """Our BGP Identifier is the higher: the new connection is told Connection Collision
    Resolution once its OPEN says so, and ours carries on untouched."""
    peer = session_peer(router_id='192.0.2.9')
    proto, theirs = connected(peer)
    run = asyncio.create_task(peer._run_session())
    replacement, connecting = incoming()
    try:
        await until(lambda: peer.fsm == FSM.OPENSENT)
        session = peer._session_task
        assert session is not None

        assert peer.handle_connection(replacement) is None
        connecting.sendall(their_open('192.0.2.2'))
        await until(lambda: replacement.io is None)

        assert notifications(connecting) == [CONNECTION_COLLISION_RESOLUTION]
        assert not session.done()
        assert peer.proto is proto and proto.connection is not None
        assert peer.fsm == FSM.OPENSENT
        assert [kind for kind, _ in negotiation.messages(negotiation.received(theirs))] == [OPEN]
    finally:
        run.cancel()
        await asyncio.gather(run, return_exceptions=True)
        negotiation.disconnect(proto, theirs)
        replacement.close()
        connecting.close()


@pytest.mark.asyncio
async def test_a_connection_held_for_its_open_is_closed_when_the_peer_stops() -> None:
    """A peer removed while the OPEN of a colliding connection is awaited takes neither."""
    peer = session_peer(router_id='192.0.2.1')
    proto, theirs = connected(peer)
    run = asyncio.create_task(peer._run_session())
    replacement, connecting = incoming()
    try:
        await until(lambda: peer.fsm == FSM.OPENSENT)
        assert peer.handle_connection(replacement) is None
        task = peer._contender_task
        assert task is not None
        peer.remove()
        assert replacement.io is None
        await until(lambda: task.done())
        assert task.cancelled()
        assert peer.proto is None and peer._contender is None
    finally:
        run.cancel()
        await asyncio.gather(run, return_exceptions=True)
        negotiation.disconnect(proto, theirs)
        replacement.close()
        connecting.close()


# ------------------------------------------------- RFC 6286 2.3, identical BGP Identifiers


def in_openconfirm_with(peer: Peer, received: Open) -> tuple[Protocol, socket.socket]:
    proto, theirs = connected(peer)
    peer.fsm.change(FSM.OPENCONFIRM)
    proto.negotiated.received_open = received
    return proto, theirs


def same_identifier_open(asn: int, four_octet_asn: int = 0) -> Open:
    capabilities = Capabilities()
    if four_octet_asn:
        capabilities[Capability.CODE.FOUR_BYTES_ASN] = ASN4(four_octet_asn)
    return Open.make_open(Version(4), ASN(asn), HoldTime(180), RouterID('192.0.2.1'), capabilities)


def collision_outcome(local_as: int, received: Open) -> str:
    """Which connection a collision with an OpenConfirm session keeps: 'ours' or 'theirs'."""
    configured = negotiation.neighbor(local_as=local_as, peer_as=0, router_id='192.0.2.1')
    peer, _ = negotiation.peer(configured)
    proto, theirs = in_openconfirm_with(peer, received)
    replacement, connecting = incoming()
    try:
        refusal = peer.handle_connection(replacement)
        if refusal is None:
            return 'theirs'
        # bounded: a NOTIFICATION fits in one write to an empty socket buffer
        for _, _ in zip(range(100), refusal):
            pass
        return 'ours'
    finally:
        negotiation.disconnect(proto, theirs)
        replacement.close()
        connecting.close()


@pytest.mark.rfc('rfc6286#2.3-identical-identifiers-larger-as-wins')
@pytest.mark.parametrize(
    'local_as,received,kept',
    [
        (65001, same_identifier_open(65002), 'theirs'),
        (65001, same_identifier_open(65000), 'ours'),
        (65001, same_identifier_open(23456, 4200000000), 'theirs'),
        (4200000001, same_identifier_open(23456, 4200000000), 'ours'),
    ],
    ids=['their-as-larger', 'our-as-larger', 'their-four-octet-as-larger', 'our-four-octet-as-larger'],
)
def test_identical_identifiers_keep_the_connection_of_the_larger_as(local_as: int, received: Open, kept: str) -> None:
    """The comparison of identifiers says nothing when they are equal: the AS numbers decide,
    the four-octet ones, not the AS_TRANS a speaker beyond two octets puts in its OPEN."""
    assert collision_outcome(local_as, received) == kept


def test_a_connection_which_sent_no_open_is_closed_without_a_cease() -> None:
    """Before our OPEN there is no BGP session to tell: RFC 4271 8.2.2 only drops the TCP connection."""
    peer = session_peer()
    proto, theirs = connected(peer)
    peer.fsm.change(FSM.CONNECT)
    replacement, connecting = incoming()
    try:
        assert peer.handle_connection(replacement) is None
        assert proto.connection is None
        assert negotiation.received(theirs) == b''
    finally:
        theirs.close()
        replacement.close()
        connecting.close()


# ------------------------------------------------------------------ RFC 4486 4, removal and shutdown


@pytest.mark.parametrize('state', [FSM.OPENSENT, FSM.OPENCONFIRM, FSM.ESTABLISHED], ids=lambda s: s.name)
@pytest.mark.rfc('rfc4486#4-peer-de-configured')
def test_a_removed_peer_is_sent_peer_de_configured(state: FSMState) -> None:
    peer = session_peer()
    proto, theirs = connected(peer)
    peer.fsm.change(state)
    try:
        peer.remove()
        assert notifications(theirs) == [PEER_DE_CONFIGURED]
        assert peer.proto is None
    finally:
        theirs.close()


@pytest.mark.rfc('rfc4486#4-administrative-shutdown')
def test_a_shutdown_sends_administrative_shutdown() -> None:
    peer = session_peer()
    proto, theirs = connected(peer)
    peer.fsm.change(FSM.ESTABLISHED)
    try:
        peer.shutdown()
        assert notifications(theirs) == [ADMINISTRATIVE_SHUTDOWN]
    finally:
        theirs.close()


def test_a_shutdown_with_graceful_restart_closes_quietly() -> None:
    """The peer keeps our routes while we restart only if no NOTIFICATION ends the session (RFC 4724)."""
    peer = session_peer()
    proto, theirs = connected(peer)
    peer.neighbor.capability.graceful_restart = 120
    proto.negotiated.sent_open = negotiation.open_message([Graceful().set(Graceful.RESTART_STATE, 120, [])])
    assert proto.negotiated.sent_open.capabilities.announced(Capability.CODE.GRACEFUL_RESTART)
    peer.fsm.change(FSM.ESTABLISHED)
    try:
        peer.shutdown()
        assert notifications(theirs) == []
        assert peer.proto is None
    finally:
        theirs.close()


def test_a_peer_still_connecting_is_closed_without_a_cease() -> None:
    peer = session_peer()
    proto, theirs = connected(peer)
    peer.fsm.change(FSM.CONNECT)
    try:
        peer.remove()
        assert negotiation.received(theirs) == b''
    finally:
        theirs.close()


@pytest.mark.asyncio
async def test_a_removed_peer_stops_the_task_of_its_session() -> None:
    """The session task was left running on a connection which was gone."""
    peer = session_peer()
    proto, theirs = connected(peer)
    theirs.sendall(their_open('192.0.2.2'))
    run = asyncio.create_task(peer._run_session())
    try:
        await until(lambda: peer.fsm == FSM.OPENCONFIRM)
        session = peer._session_task
        assert session is not None
        peer.remove()
        await asyncio.wait_for(run, timeout=1)
        assert session.cancelled()
        assert notifications(theirs) == [PEER_DE_CONFIGURED]
    finally:
        run.cancel()
        await asyncio.gather(run, return_exceptions=True)
        theirs.close()


@pytest.mark.asyncio
async def test_cancelling_the_peer_task_still_cancels_it() -> None:
    """Only the session is ended by _cancel_session: a cancelled peer task stays cancelled."""
    peer = session_peer()
    proto, theirs = connected(peer)
    run = asyncio.create_task(peer._run_session())
    try:
        await until(lambda: peer._session_task is not None)
        run.cancel()
        with pytest.raises(asyncio.CancelledError):
            await run
    finally:
        negotiation.disconnect(proto, theirs)
