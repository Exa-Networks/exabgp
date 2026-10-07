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
from exabgp.bgp.message.open.capability import Capability
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
