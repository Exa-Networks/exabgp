"""draft-ietf-idr-bgp-multisession-07, sections 6, 7, 9 and 10: the sessions with one peer.

The ledger these tests are joined to is qa/rfc/draft-ietf-idr-bgp-multisession-07.toml.

A multi-session neighbour with two families is two neighbours, one per family, each with a
Peer of its own (configuration/grammar/install.py).  What these tests look at is how those
Peers live beside each other: which of them a connection from the peer reaches, what a
collision between two of them is answered with, and what an error in one does to the other.

Most of the collision procedure of section 6 is not implemented: the listener hands an
incoming connection to the first Peer whose addresses match, before its OPEN is read, and
that Peer applies RFC 4271 section 6.8 whatever the Session Id.  The tests of those
requirements are strict xfails which show what conforming would mean.

Everything is real: the Reactor, the Listener, the Peers built from configuration text, and
TCP connections over 127.0.0.1.  The compiled build (plan/wip-mypyc.md) lets no method of
these classes be replaced.
"""

from __future__ import annotations

import asyncio
import contextlib
import gc
import socket
from typing import Any

import pytest

from exabgp.bgp.fsm import FSM
from exabgp.bgp.message import Notify
from exabgp.bgp.message.direction import Direction
from exabgp.bgp.message.open import ASN, HoldTime, Open, RouterID, Version
from exabgp.bgp.message.open.capability import Capabilities, Capability
from exabgp.bgp.message.open.capability.mp import MultiProtocol
from exabgp.bgp.message.open.capability.ms import MultiSession
from exabgp.bgp.message.open.capability.negotiated import Negotiated
from exabgp.bgp.neighbor import NeighborTemplate
from exabgp.configuration.configuration import Configuration
from exabgp.protocol.family import AFI, SAFI, FamilyTuple
from exabgp.reactor.listener import Listener
from exabgp.reactor.loop import Reactor
from exabgp.reactor.network.incoming import Incoming
from exabgp.reactor.peer import Peer
from exabgp.rib import RIB
from tests.negotiation import api_asks, messages, reactor
from tests.wire_reader import tcp_socketpair

MULTISESSION = Capability.CODE.MULTISESSION
MULTIPROTOCOL = Capability.CODE.MULTIPROTOCOL

IPV4_UNICAST: FamilyTuple = (AFI.ipv4, SAFI.unicast)
IPV6_UNICAST: FamilyTuple = (AFI.ipv6, SAFI.unicast)

NOTIFICATION = 3
OPEN_MESSAGE_ERROR = 2
CEASE = 6

# ours is 192.0.2.2, so on a collision RFC 4271 6.8 keeps our connection and refuses theirs
OUR_ROUTER_ID = '192.0.2.2'
THEIR_ROUTER_ID = '192.0.2.1'

MULTISESSION_NEIGHBOR = f"""
neighbor 127.0.0.1 {{
    router-id {OUR_ROUTER_ID};
    local-address 127.0.0.1;
    local-as 65001;
    peer-as 65002;
    capability {{ multi-session enable; }}
    family {{ ipv4 unicast; ipv6 unicast; }}
}}
"""

# a second neighbour with the peer, for IPv4 unicast again: its session collides with the
# IPv4 session of the first, same addresses and the same Session Id values.  Its router-id
# is what makes its name, and so its Peer, a different one
COLLIDING_NEIGHBOR = """
neighbor 127.0.0.1 {
    router-id 192.0.2.3;
    local-address 127.0.0.1;
    local-as 65001;
    peer-as 65002;
    capability { multi-session enable; }
    family { ipv4 unicast; }
}
"""

# bounded: a NOTIFICATION fits in one write to an empty socket buffer
MAX_WRITER_STEPS = 100
# bounded: how long a Peer is given to open a connection, in steps of SETTLE_SECONDS
MAX_CONNECT_STEPS = 200
SETTLE_SECONDS = 0.01
# bounded: an OPEN exchange cut short by a NOTIFICATION over loopback
SESSION_SECONDS = 5.0
# how long a write takes to be readable at the other end of a loopback connection
LOOPBACK_SECONDS = 0.05


@pytest.fixture(autouse=True)
def isolated_ribs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(RIB, '_cache', {})


# ==============================================================================
# Helpers
# ==============================================================================


class Sessions:
    """The Peers of the configuration, on one real Reactor, found by name or by family."""

    def __init__(self, *blocks: str) -> None:
        # one text: each entry of the list is a configuration of its own, read one at a time
        configuration = Configuration([''.join(blocks)], text=True)
        assert configuration.reload(), str(configuration.error)
        self.reactor: Reactor = reactor()[0]
        self.peers: dict[str, Peer] = {}
        for key, neighbor in configuration.neighbors.items():
            api_asks(neighbor)
            peer = Peer(neighbor, self.reactor)
            self.reactor.register_peer(key, peer)
            self.peers[key] = peer
        self._held: list[socket.socket] = []

    def of(self, family: FamilyTuple) -> Peer:
        """The one Peer of the first configured neighbour carrying this family."""
        for peer in self.peers.values():
            if peer.neighbor.families() == [family]:
                return peer
        raise AssertionError(f'no session for {family}')

    def established(self, peer: Peer) -> socket.socket:
        """Give the Peer a live connection and the ESTABLISHED state; the far end is returned."""
        return self.connected(peer, FSM.ESTABLISHED)

    def connected(self, peer: Peer, state: Any) -> socket.socket:
        connection, far = incoming()
        assert peer.handle_connection(connection) is None, 'an idle Peer accepts a connection'
        peer.fsm.change(state)
        self._held.append(far)
        return far

    def close(self) -> None:
        for peer in self.peers.values():
            if peer.proto is not None:
                peer.proto.close('test over')
                peer.proto = None
        for far in self._held:
            far.close()


@pytest.fixture
def sessions() -> Any:
    built = Sessions(MULTISESSION_NEIGHBOR)
    yield built
    built.close()


def incoming() -> tuple[Incoming, socket.socket]:
    """A real accepted TCP connection, and the socket of the side which connected."""
    accepted, connecting = tcp_socketpair()
    return Incoming(AFI.ipv4, '127.0.0.1', '127.0.0.1', accepted), connecting


def open_from_the_peer(family: FamilyTuple, session_id: Capability.CODE = MULTIPROTOCOL) -> bytes:
    """The OPEN the peer sends for the session of this family, with this Session Id."""
    capabilities = Capabilities()
    multiprotocol = MultiProtocol()
    multiprotocol.extend([family])
    capabilities[MULTIPROTOCOL] = multiprotocol
    capabilities[MULTISESSION] = MultiSession().set([session_id])
    message = Open.make_open(Version(4), ASN(65002), HoldTime(180), RouterID(THEIR_ROUTER_ID), capabilities)
    return message.pack_message(Negotiated.UNSET)


def received_open(family: FamilyTuple) -> Open:
    """What the Peer of a session in OPENCONFIRM has read from the peer."""
    message = Open.unpack_message(open_from_the_peer(family)[19:], Negotiated.UNSET)
    assert isinstance(message, Open)
    return message


def dispatched(built: Sessions, sent: bytes) -> socket.socket:
    """Connect to a real Listener of the reactor, send `sent`, and let the listener dispatch.

    The far end of the connection is returned, for the test to see what it was told.
    """
    listener = Listener(built.reactor)
    listener.serving = True
    with socket.create_server(('127.0.0.1', 0)) as listening:
        far = socket.create_connection(listening.getsockname())
        built._held.append(far)
        far.sendall(sent)
        accepted, _ = listening.accept()
        listener._accepted[listening] = accepted
        for _ in listener.new_connections():
            pass
    # a connection nobody holds any more is closed now, not whenever the collector runs
    gc.collect()
    return far


def still_open(far: socket.socket) -> bool:
    """Whether our side of the connection is still open, with nothing sent to the far end."""
    far.setblocking(False)
    try:
        far.recv(1)
    except BlockingIOError:
        return True
    except ConnectionResetError:
        # closed with the OPEN the far end sent still unread
        return False
    return False


def pending(far: socket.socket) -> bytes:
    """What the far end can read once what was written has crossed the loopback."""
    far.settimeout(LOOPBACK_SECONDS)
    try:
        return far.recv(4096)
    except (TimeoutError, ConnectionResetError):
        return b''


def told(refusal: Any, far: socket.socket) -> list[tuple[int, int]]:
    """Run the refusal handle_connection returned, and the (code, subcode) the peer read.

    The far end reads after each step: our side closes with the far end's OPEN unread,
    which resets the connection, and a reset discards what had not been read yet.
    """
    assert refusal is not None, 'the connection was accepted, not refused'
    data = b''
    for step, _ in enumerate(refusal):
        assert step < MAX_WRITER_STEPS, 'the NOTIFICATION was never written'
        data += pending(far)
    return [(body[0], body[1]) for kind, body in messages(data) if kind == NOTIFICATION]


async def connects_out(peer: Peer, listening: socket.socket) -> bool:
    """Run the Peer as the reactor does, and whether it opened a connection to `listening`."""
    task = asyncio.create_task(peer.run())
    try:
        for _ in range(MAX_CONNECT_STEPS):
            await asyncio.sleep(SETTLE_SECONDS)
            try:
                accepted, _ = listening.accept()
            except BlockingIOError:
                continue
            accepted.close()
            return True
        return False
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


def attempts_a_session(built: Sessions, peer: Peer) -> bool:
    """Whether the Peer, run by itself, tries to open a session with the peer."""
    with socket.create_server(('127.0.0.1', 0)) as listening:
        listening.setblocking(False)
        peer.neighbor.session.connect = listening.getsockname()[1]
        return asyncio.run(connects_out(peer, listening))


def reset_by_a_notification(built: Sessions, peer: Peer, notify: Notify) -> None:
    """Run the Peer's session until the peer ends it with this NOTIFICATION, in place of its OPEN."""
    far = built.connected(peer, FSM.IDLE)
    far.sendall(notify.notification.pack_message(Negotiated.UNSET))
    asyncio.run(asyncio.wait_for(peer._run(), SESSION_SECONDS))
    assert peer.proto is None, 'the NOTIFICATION reset the session'


# ==============================================================================
# Section 6: modified connection collision handling
# ==============================================================================


def test_a_session_connects_out_while_a_session_of_another_group_is_established(sessions: Sessions) -> None:
    """The IPv6 session does not collide with the IPv4 one, so nothing holds it back.

    It is also what shows `attempts_a_session` sees a connection when one is made.
    """
    sessions.established(sessions.of(IPV4_UNICAST))

    assert attempts_a_session(sessions, sessions.of(IPV6_UNICAST))


@pytest.mark.rfc('draft-ietf-idr-bgp-multisession-07#6-evaluate-before-connecting')
@pytest.mark.xfail(
    strict=True,
    reason='each Peer decides alone whether to connect, and none looks at the sessions of the others with the peer',
)
def test_no_session_is_attempted_which_would_collide_with_an_established_one() -> None:
    """Two neighbours each have an IPv4 unicast session with the peer, with the same Session Id.

    Once one is ESTABLISHED the other would collide with it, and section 6 goes on: the
    speaker "SHOULD NOT attempt creating new session".
    """
    built = Sessions(MULTISESSION_NEIGHBOR, COLLIDING_NEIGHBOR)
    try:
        first, second = [peer for peer in built.peers.values() if peer.neighbor.families() == [IPV4_UNICAST]]
        built.established(first)

        assert not attempts_a_session(built, second)
    finally:
        built.close()


def test_an_open_which_fully_matches_the_established_session_is_closed(sessions: Sessions) -> None:
    """The outcome of the first half of the requirement holds: the old session stays.

    It holds by RFC 4271 6.8 rather than by evaluating the OPEN, so the requirement is not
    marked here; its other side is the test after this one.
    """
    ipv4 = sessions.of(IPV4_UNICAST)
    sessions.established(ipv4)
    kept = ipv4.proto

    far = dispatched(sessions, open_from_the_peer(IPV4_UNICAST))

    assert not still_open(far)
    assert ipv4.proto is kept
    assert ipv4.fsm == FSM.ESTABLISHED


@pytest.mark.rfc('draft-ietf-idr-bgp-multisession-07#6-established-session-wins-a-full-match', polarity='negative')
@pytest.mark.xfail(
    strict=True,
    reason='the established Peer refuses the connection before its OPEN is read, whatever its Session Id',
)
def test_an_open_which_does_not_match_the_established_session_is_not_closed(sessions: Sessions) -> None:
    """Only an OPEN which fully matches the established session is to be closed for it."""
    sessions.established(sessions.of(IPV4_UNICAST))

    far = dispatched(sessions, open_from_the_peer(IPV6_UNICAST))

    assert still_open(far), 'the connection for the IPv6 session was closed'


@pytest.mark.rfc('draft-ietf-idr-bgp-multisession-07#6-unique-sessions-may-both-establish')
@pytest.mark.xfail(
    strict=True,
    reason='the listener gives the connection to the first Peer of the address, the established IPv4 one',
)
def test_a_connection_for_another_group_reaches_its_own_session(sessions: Sessions) -> None:
    ipv4 = sessions.of(IPV4_UNICAST)
    ipv6 = sessions.of(IPV6_UNICAST)
    sessions.established(ipv4)

    dispatched(sessions, open_from_the_peer(IPV6_UNICAST))

    assert ipv4.fsm == FSM.ESTABLISHED
    assert ipv6.proto is not None, 'the IPv6 session was not given the connection'


@pytest.mark.rfc('draft-ietf-idr-bgp-multisession-07#6-no-rfc4271-collision-for-unique-sessions')
@pytest.mark.xfail(
    strict=True,
    reason='RFC 4271 6.8 is applied by the first Peer of the address before the OPEN is read, whatever the Session Ids',
)
def test_a_session_in_opensent_is_not_closed_for_a_session_of_another_group(sessions: Sessions) -> None:
    ipv4 = sessions.of(IPV4_UNICAST)
    sessions.connected(ipv4, FSM.OPENSENT)
    kept = ipv4.proto

    dispatched(sessions, open_from_the_peer(IPV6_UNICAST))

    assert ipv4.proto is kept, 'the IPv4 session was closed by RFC 4271 6.8'


@pytest.mark.rfc('draft-ietf-idr-bgp-multisession-07#6-rfc4271-collision-for-colliding-sessions')
@pytest.mark.rfc('draft-ietf-idr-bgp-multisession-07#6-collision-notification')
@pytest.mark.xfail(
    strict=True,
    reason='a collision is answered with Cease 6/7, the RFC 4271 NOTIFICATION, whether multisession is on or not',
)
def test_a_collision_is_answered_with_an_open_message_error(sessions: Sessions) -> None:
    """Two connections for the IPv4 session collide, and RFC 4271 6.8 keeps ours, the higher id.

    The procedure is the one of 6.8, but the NOTIFICATION is "as described in this
    document", which only defines subcodes of OPEN Message Error.  The draft names none of
    them for a collision, so this asks for the code alone.
    """
    ipv4 = sessions.of(IPV4_UNICAST)
    sessions.connected(ipv4, FSM.OPENCONFIRM)
    assert ipv4.proto is not None
    ipv4.proto.negotiated.received_open = received_open(IPV4_UNICAST)
    kept = ipv4.proto
    connection, far = incoming()
    far.sendall(open_from_the_peer(IPV4_UNICAST))

    try:
        ((code, _),) = told(ipv4.handle_connection(connection), far)
    finally:
        far.close()

    assert ipv4.proto is kept
    assert code == OPEN_MESSAGE_ERROR, f'the collision was answered with code {code}'


# ==============================================================================
# Section 7: connection establishment
# ==============================================================================


@pytest.mark.rfc('draft-ietf-idr-bgp-multisession-07#7-matching-session-id-checks-collisions', polarity='negative')
@pytest.mark.xfail(
    strict=True,
    reason='the collision is decided before the OPEN is read, so its Session Id is never compared first',
)
def test_a_session_id_mismatch_is_a_grouping_conflict_even_beside_an_established_session(sessions: Sessions) -> None:
    """Collisions are checked only once the received Session Id matches ours.

    A peer whose Session Id does not match is told Grouping Conflict, which section 7 says
    first, and not that its connection collided with the established session.
    """
    ipv4 = sessions.of(IPV4_UNICAST)
    sessions.established(ipv4)
    connection, far = incoming()
    far.sendall(open_from_the_peer(IPV4_UNICAST, session_id=Capability.CODE.ROUTE_REFRESH))

    try:
        sent = told(ipv4.handle_connection(connection), far)
    finally:
        far.close()

    assert sent == [(OPEN_MESSAGE_ERROR, 8)]


# ==============================================================================
# Section 9: error handling
# ==============================================================================


@pytest.mark.rfc('draft-ietf-idr-bgp-multisession-07#9-reset-only-the-affected-session')
def test_an_error_resets_only_the_session_it_happened_on(sessions: Sessions) -> None:
    ipv4 = sessions.of(IPV4_UNICAST)
    ipv6 = sessions.of(IPV6_UNICAST)
    ipv6_far = sessions.established(ipv6)
    ipv6_session = ipv6.proto

    reset_by_a_notification(sessions, ipv4, Notify(6, 2, 'shut down'))

    assert ipv6.proto is ipv6_session
    assert ipv6.fsm == FSM.ESTABLISHED
    assert still_open(ipv6_far)


@pytest.mark.rfc('draft-ietf-idr-bgp-multisession-07#9-reset-only-the-affected-session', polarity='negative')
def test_an_error_resets_the_session_it_happened_on(sessions: Sessions) -> None:
    """The other side: the affected session itself is reset, its connection closed."""
    ipv4 = sessions.of(IPV4_UNICAST)
    sessions.established(sessions.of(IPV6_UNICAST))

    reset_by_a_notification(sessions, ipv4, Notify(6, 2, 'shut down'))

    assert ipv4.fsm == FSM.IDLE
    assert ipv4.proto is None


# ==============================================================================
# Section 10: configuration and management
# ==============================================================================


@pytest.mark.rfc('draft-ietf-idr-bgp-multisession-07#10-view-each-group')
@pytest.mark.xfail(
    strict=True,
    reason='show neighbor reports the state and message counters of each session, not the NOTIFICATION which reset it',
)
def test_each_group_shows_its_state_and_the_notification_which_reset_it(sessions: Sessions) -> None:
    ipv4 = sessions.of(IPV4_UNICAST)
    ipv6 = sessions.of(IPV6_UNICAST)
    sessions.established(ipv6)
    reset_by_a_notification(sessions, ipv4, Notify(6, 2, 'shut down'))

    shown = {peer: NeighborTemplate.extensive(peer.cli_data()) for peer in (ipv4, ipv6)}

    assert 'ESTABLISHED' in shown[ipv6]
    assert 'ESTABLISHED' not in shown[ipv4]
    assert 'Administrative Shutdown' in shown[ipv4], 'the NOTIFICATION which reset the session is not shown'


@pytest.mark.rfc('draft-ietf-idr-bgp-multisession-07#10-no-hard-coded-group-restrictions')
@pytest.mark.xfail(
    strict=True,
    reason='a multi-session neighbour is always split one family per session, configuration/grammar/install.py',
)
def test_a_peer_grouping_two_families_in_one_session_is_served() -> None:
    """The peer puts IPv4 and IPv6 unicast in one session, Session Id MULTIPROTOCOL.

    With groups the operator can shape, one of ours could carry both and match it exactly
    (section 7, case 1).  Hard-coded trivial groups give two partial matches, case 3, and
    every one of our sessions answers Grouping Conflict.
    """
    configuration = Configuration([MULTISESSION_NEIGHBOR], text=True)
    assert configuration.reload(), str(configuration.error)
    both = MultiProtocol()
    both.extend([IPV4_UNICAST, IPV6_UNICAST])
    theirs = Capabilities()
    theirs[MULTIPROTOCOL] = both
    theirs[MULTISESSION] = MultiSession().set([MULTIPROTOCOL])
    offer = Open.make_open(Version(4), ASN(65002), HoldTime(180), RouterID(THEIR_ROUTER_ID), theirs)

    answers = []
    for neighbor in configuration.neighbors.values():
        negotiated = Negotiated.make_negotiated(neighbor, Direction.OUT)
        ours = Capabilities().new(neighbor, False)
        negotiated.sent(Open.make_open(Version(4), ASN(65001), HoldTime(180), RouterID(OUR_ROUTER_ID), ours))
        negotiated.received(offer)
        answers.append(negotiated.multisession)

    assert True in answers, f'every session refused the peer: {answers}'
