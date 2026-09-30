#!/usr/bin/env python3
# encoding: utf-8
"""test_peer_state_machine.py

Comprehensive tests for BGP Peer State Machine implementation.
Tests state transitions, timers, collision detection, and error recovery.

The Peer is a real one, over a real Reactor and a neighbour read from a configuration:
the compiled build (plan/wip-mypyc.md) checks the declared type of each argument and
attribute, so a Mock can stand in for none of them, and a method of a compiled instance
cannot be replaced.  What the tests used to learn by asking a Mock whether it was called,
they learn from what the call left behind: the RIB's queues, the RIB cache, the bytes a
connection sent.

Created: 2025-11-08
"""

import asyncio
import os
from typing import Any
from unittest.mock import Mock, patch

import pytest

# Set up environment before importing ExaBGP modules
os.environ['exabgp_log_enable'] = 'false'
os.environ['exabgp_log_level'] = 'CRITICAL'
os.environ['exabgp_tcp_bind'] = '127.0.0.1'
os.environ['exabgp_tcp_attempts'] = '0'

from exabgp.bgp.fsm import FSM  # noqa: E402
from exabgp.bgp.message import KeepAlive, Open  # noqa: E402
from exabgp.bgp.message.notification import Notify  # noqa: E402
from exabgp.bgp.message.open import ASN, Capabilities, HoldTime, RouterID, Version  # noqa: E402
from exabgp.bgp.message.open.capability.negotiated import Negotiated  # noqa: E402
from exabgp.bgp.neighbor import Neighbor  # noqa: E402
from exabgp.configuration.configuration import Configuration  # noqa: E402
from exabgp.protocol.family import AFI, SAFI  # noqa: E402
from exabgp.reactor.network.incoming import Incoming  # noqa: E402
from exabgp.reactor.peer import Peer, Stats  # noqa: E402
from exabgp.reactor.protocol import Protocol  # noqa: E402
from exabgp.rib import RIB  # noqa: E402
from tests.negotiation import connect, messages, negotiated, peer as real_peer, received  # noqa: E402
from tests.wire_reader import tcp_socketpair  # noqa: E402

from exabgp.reactor.peer import peer as peer_module  # noqa: E402

# a compiled module is an extension, with no .py file behind it
COMPILED = not str(peer_module.__file__).endswith('.py')

NOTIFICATION = 3
KEEPALIVE = 4
IPV4_UNICAST = (AFI.ipv4, SAFI.unicast)
IPV6_UNICAST = (AFI.ipv6, SAFI.unicast)


@pytest.fixture(autouse=True)
def mock_logger() -> Any:
    """Mock the logger to avoid initialization issues."""
    from exabgp.logger.option import option

    # Save original values
    original_logger = option.logger
    original_formater = option.formater

    # Create a mock logger with all required methods
    mock_option_logger = Mock()
    mock_option_logger.debug = Mock()
    mock_option_logger.info = Mock()
    mock_option_logger.warning = Mock()
    mock_option_logger.error = Mock()
    mock_option_logger.critical = Mock()
    mock_option_logger.fatal = Mock()

    # Create a mock formater that accepts all arguments
    mock_formater = Mock(return_value='formatted message')

    option.logger = mock_option_logger
    option.formater = mock_formater

    yield

    # Restore original values
    option.logger = original_logger
    option.formater = original_formater


def configured(
    *families: str,
    routes: tuple[str, ...] = (),
    router_id: str = '192.0.2.2',
    neighbor: str = '192.0.2.1',
) -> Neighbor:
    """A neighbour as the configuration builds it, with its RIB enabled."""
    family = ' '.join(f'{name};' for name in families or ('ipv4 unicast',))
    static = ' '.join(f'route {route};' for route in routes)
    config = Configuration(
        [
            f"""neighbor {neighbor} {{
            router-id {router_id};
            local-address 192.0.2.2;
            local-as 65001;
            peer-as 65002;
            family {{ {family} }}
            static {{ {static} }}
        }}"""
        ],
        text=True,
    )
    assert config.reload(), str(config.error)
    return next(iter(config.neighbors.values()))


def make_peer(neighbor: Neighbor | None = None) -> Peer:
    session, _ = real_peer(configured() if neighbor is None else neighbor)
    return session


def queued(neighbor: Neighbor) -> list[str]:
    """The prefixes the outgoing RIB has queued to announce."""
    return sorted(str(route.nlri.cidr) for route in neighbor.rib.outgoing.queued_routes())


def queue_a_route(neighbor: Neighbor, prefix: str = '10.9.9.0/24') -> None:
    """Queue one route for announcement, as the API does."""
    (route,) = configured(routes=(f'{prefix} next-hop 192.0.2.1',), neighbor='192.0.2.99').routes
    neighbor.rib.outgoing.add_to_rib(route)
    assert neighbor.rib.outgoing.pending()


def incoming() -> tuple[Incoming, Any]:
    """A real accepted TCP connection, and the socket of the side which connected."""
    accepted, connecting = tcp_socketpair()
    return Incoming(AFI.ipv4, '127.0.0.1', '127.0.0.1', accepted), connecting


def notifications_sent(refusal: Any, connecting: Any) -> list[tuple[int, int]]:
    """Run the refusal handle_connection returned, and the (code, subcode) the peer read."""
    # bounded: a NOTIFICATION fits in one write to an empty socket buffer
    for _, _ in zip(range(100), refusal):
        pass
    # the refusal closes the connection once it is written: read up to that end of stream
    connecting.settimeout(5)
    data = b''
    try:
        # bounded: each read takes at least a byte, or ends the loop
        for _ in range(1024):
            chunk = connecting.recv(65536)
            if not chunk:
                break
            data += chunk
    finally:
        connecting.close()
    return [(body[0], body[1]) for kind, body in messages(data) if kind == NOTIFICATION]


def received_open(router_id: str) -> Open:
    return Open.make_open(Version(4), ASN(65002), HoldTime(180), RouterID(router_id), Capabilities())


class TestPeerInitialization:
    """Test Peer object initialization"""

    def test_peer_init_basic(self) -> None:
        """Test basic Peer initialization"""
        neighbor = configured()
        session, _ = real_peer(neighbor)
        reactor = session.reactor

        peer = Peer(neighbor, reactor)

        assert peer.neighbor is neighbor
        assert peer.reactor is reactor
        assert peer.fsm == FSM.IDLE
        assert peer.proto is None
        assert peer._restart is True
        assert peer._restarted is True

    def test_peer_init_stats(self) -> None:
        """Test Peer initialization creates stats"""
        peer = make_peer()

        assert 'fsm' in peer.stats
        assert 'creation' in peer.stats
        assert 'reset' in peer.stats
        assert 'complete' in peer.stats
        assert 'up' in peer.stats
        assert 'down' in peer.stats

    def test_peer_init_message_counters(self) -> None:
        """Test Peer initialization creates message counters"""
        peer = make_peer()

        assert peer.stats['receive-open'] == 0
        assert peer.stats['send-open'] == 0
        assert peer.stats['receive-keepalive'] == 0
        assert peer.stats['send-keepalive'] == 0
        assert peer.stats['receive-update'] == 0
        assert peer.stats['send-update'] == 0
        assert peer.stats['receive-notification'] == 0
        assert peer.stats['send-notification'] == 0

    def test_peer_id_generation(self) -> None:
        """Test Peer generates its ID from the neighbour's uid"""
        neighbor = configured()
        peer = make_peer(neighbor)

        assert peer.id() == f'peer-{neighbor.uid}'


class TestPeerStateTransitions:
    """Test Peer state transitions through FSM"""

    def test_peer_starts_in_idle(self) -> None:
        """Test Peer starts in IDLE state"""
        peer = make_peer()

        assert peer.fsm == FSM.IDLE

    def test_peer_close_transitions_to_idle(self) -> None:
        """Test _close transitions Peer to IDLE"""
        peer = make_peer()
        peer.fsm.change(FSM.ESTABLISHED)

        peer._close('test close')

        assert peer.fsm == FSM.IDLE
        assert peer.proto is None

    def test_peer_reset_clears_state(self) -> None:
        """Test _reset clears peer state, and resets the neighbour's RIB"""
        neighbor = configured()
        peer = make_peer(neighbor)
        peer.fsm.change(FSM.ESTABLISHED)
        queue_a_route(neighbor)

        peer._reset('test reset')

        assert peer.fsm == FSM.IDLE
        assert not peer.fsm_runner.running
        assert not peer.fsm_runner.terminated
        assert peer._teardown is None
        # reset_rib: what was queued for the session which ended is not sent to the next
        assert not neighbor.rib.outgoing.pending()

    def test_peer_stop_sets_flags(self) -> None:
        """Test stop() sets correct flags, and takes the RIB out of the cache"""
        neighbor = configured()
        peer = make_peer(neighbor)
        assert RIB._cache.get(neighbor.rib.name) is neighbor.rib

        peer.stop()

        assert peer._restart is False
        assert peer._restarted is False
        assert peer.fsm == FSM.IDLE
        assert neighbor.rib.name not in RIB._cache

    def test_peer_reestablish_sets_teardown(self) -> None:
        """Test reestablish() sets teardown flag"""
        peer = make_peer()

        peer.reestablish()

        assert peer._teardown is not None
        assert (peer._teardown.code, peer._teardown.subcode) == (6, 3)
        assert peer._restart is True
        assert peer._restarted is True


class TestPeerCollisionDetection:
    """Test Peer collision detection logic"""

    def test_collision_reject_when_established(self) -> None:
        """Test collision detection rejects connection when established"""
        peer = make_peer()
        peer.fsm.change(FSM.ESTABLISHED)
        connection, connecting = incoming()

        result = peer.handle_connection(connection)

        assert result is not None
        assert notifications_sent(result, connecting) == [(6, 7)]

    def test_collision_detection_openconfirm_higher_router_id(self) -> None:
        """Test collision detection in OPENCONFIRM with higher local router-id"""
        peer = make_peer(configured(router_id='2.2.2.2'))
        peer.fsm.change(FSM.OPENCONFIRM)
        peer.proto = Protocol(peer)
        peer.proto.negotiated.received_open = received_open('1.1.1.1')
        connection, connecting = incoming()

        result = peer.handle_connection(connection)

        # Should reject incoming connection (local ID is higher)
        assert result is not None
        assert notifications_sent(result, connecting) == [(6, 7)]

    def test_collision_detection_openconfirm_lower_router_id(self) -> None:
        """Test collision detection in OPENCONFIRM with lower local router-id"""
        peer = make_peer(configured(router_id='1.1.1.1'))
        peer.fsm.change(FSM.OPENCONFIRM)
        existing = Protocol(peer)
        existing.negotiated.received_open = received_open('2.2.2.2')
        theirs = connect(existing)
        peer.proto = existing
        connection, connecting = incoming()

        try:
            result = peer.handle_connection(connection)

            # Should accept incoming connection (local ID is lower)
            assert result is None
            assert peer.proto is not None
            assert peer.proto is not existing
            assert peer.proto.connection is connection
            # the outgoing connection was closed for the incoming one
            assert existing.connection is None
        finally:
            connection.close()
            connecting.close()
            theirs.close()

    def test_collision_accept_replaces_proto(self) -> None:
        """Test accepting collision replaces existing protocol"""
        peer = make_peer()
        peer.fsm.change(FSM.ACTIVE)
        old_proto = Protocol(peer)
        peer.proto = old_proto
        connection, connecting = incoming()

        try:
            result = peer.handle_connection(connection)

            # Should accept connection and replace proto
            assert result is None
            assert peer.proto is not old_proto
            assert peer.proto is not None
            assert peer.proto.connection is connection
            assert not peer.fsm_runner.running
        finally:
            connection.close()
            connecting.close()


class TestPeerTimers:
    """Test Peer timer functionality"""

    def test_receive_timer_initialized(self) -> None:
        """Test receive timer is only initialized after OPENCONFIRM"""
        peer = make_peer()

        assert peer.recv_timer is None

    def test_peer_delay_increase_on_close(self) -> None:
        """Test delay increases on connection close"""
        peer = make_peer()
        initial_next = peer._delay._next

        peer._close('test')

        # Delay should increase after close (tracked by _next value)
        assert peer._delay._next > initial_next

    def test_peer_delay_reset_on_reestablish(self) -> None:
        """Test delay resets on reestablish"""
        peer = make_peer()
        peer._delay.increase()
        peer._delay.increase()

        peer.reestablish()

        # Delay should be reset (_next should be 0)
        assert peer._delay._next == 0

    def test_peer_delay_reset_on_teardown(self) -> None:
        """Test delay resets on teardown"""
        peer = make_peer()
        peer._delay.increase()

        peer.teardown(Notify(6, 3), restart=True)

        # Delay should be reset (_next should be 0)
        assert peer._delay._next == 0


class TestPeerErrorRecovery:
    """Test Peer error recovery mechanisms"""

    def test_peer_close_on_error_transitions_to_idle(self) -> None:
        """Test _close transitions peer to IDLE on error"""
        peer = make_peer()
        peer.fsm.change(FSM.ESTABLISHED)

        peer._close('test error', 'network error')

        # Should transition to IDLE after error
        assert peer.fsm == FSM.IDLE

    def test_peer_reset_on_error_clears_state(self) -> None:
        """Test _reset clears peer state on error"""
        neighbor = configured()
        peer = make_peer(neighbor)
        peer.fsm.change(FSM.ESTABLISHED)
        peer._teardown = Notify(6, 6)
        queue_a_route(neighbor)

        peer._reset('notification received', 'error')

        # Should reset state
        assert peer.fsm == FSM.IDLE
        assert peer._teardown is None
        assert not neighbor.rib.outgoing.pending()

    def test_peer_handles_network_error_state(self) -> None:
        """Test Peer error handling transitions to IDLE"""
        peer = make_peer()
        peer.fsm.change(FSM.OPENCONFIRM)

        # Simulate error by calling _reset
        peer._reset('network error')

        assert peer.fsm == FSM.IDLE

    def test_peer_error_increases_delay(self) -> None:
        """Test error increases backoff delay"""
        peer = make_peer()
        initial_next = peer._delay._next

        # Simulate error
        peer._close('test error')

        # Delay should increase
        assert peer._delay._next > initial_next

    def test_peer_clears_proto_on_error(self) -> None:
        """Test Peer clears, and closes, its protocol on error"""
        peer = make_peer()
        proto = Protocol(peer)
        theirs = connect(proto)
        peer.proto = proto

        try:
            peer._close('test error')

            # Protocol should be cleared, and its connection closed
            assert peer.proto is None
            assert proto.connection is None
        finally:
            theirs.close()


class TestPeerConnectionAttempts:
    """Test Peer connection attempt limiting"""

    def test_can_reconnect_unlimited(self) -> None:
        """Test can_reconnect with unlimited attempts"""
        peer = make_peer()
        peer.max_connection_attempts = 0  # unlimited, what tcp.attempts 0 gives

        assert peer.can_reconnect() is True
        peer.connection_attempts = 1000
        assert peer.can_reconnect() is True

    def test_can_reconnect_limited(self) -> None:
        """Test can_reconnect with limited attempts"""
        peer = make_peer()
        peer.max_connection_attempts = 3

        assert peer.can_reconnect() is True
        peer.connection_attempts = 2
        assert peer.can_reconnect() is True
        peer.connection_attempts = 3
        assert peer.can_reconnect() is False
        peer.connection_attempts = 4
        assert peer.can_reconnect() is False

    def test_connection_attempt_counting(self) -> None:
        """Test connection attempts are tracked"""
        peer = make_peer()
        peer.max_connection_attempts = 3

        # Initially no attempts
        assert peer.connection_attempts == 0

        # Simulate attempts
        peer.connection_attempts = 2
        assert peer.can_reconnect() is True

        peer.connection_attempts = 3
        assert peer.can_reconnect() is False

    def test_the_attempt_limit_is_read_from_the_environment(self) -> None:
        """tcp.attempts, which the environment of this file sets to 0, is the peer's limit"""
        from exabgp.environment import getenv

        assert make_peer().max_connection_attempts == getenv().tcp.attempts

    @pytest.mark.asyncio
    async def test_establishment_negotiates_each_open_once(self) -> None:
        """A session established over a real connection, each OPEN handed to Negotiated once.

        The OPEN exchange runs for real: ours is written to the peer's socket, and the
        peer's OPEN and KEEPALIVE are read from it.  Counting the calls needs Negotiated's
        methods replaced, which a compiled class does not allow, so the count is only
        checked interpreted; the establishment is checked both ways.
        """
        peer = make_peer()
        peer.connection_attempts = 3
        proto = Protocol(peer)
        theirs = connect(proto)
        peer.proto = proto
        wire = negotiated()
        theirs.sendall(received_open('192.0.2.1').pack_message(wire) + KeepAlive.make_keepalive().pack_message(wire))

        calls: dict[str, int] = {'sent': 0, 'received': 0}
        counting = []
        if not COMPILED:
            for name in calls:

                def counted(self: Negotiated, message: Open, _name: str = name, _real: Any = getattr(Negotiated, name)):
                    calls[_name] += 1
                    return _real(self, message)

                counting.append(patch.object(Negotiated, name, counted))
        for each in counting:
            each.start()
        try:
            await asyncio.wait_for(peer._establish(), timeout=5)
        finally:
            for each in counting:
                each.stop()
            sent = messages(received(theirs))
            theirs.close()
            proto.close()

        assert peer.fsm == FSM.ESTABLISHED
        # _connect was not needed, the connection was there: no attempt was counted
        assert peer.connection_attempts == 3
        assert [kind for kind, _ in sent] == [1, KEEPALIVE]
        assert proto.negotiated.sent_open is not None
        assert proto.negotiated.received_open is not None
        assert proto.negotiated.peer_as == ASN(65002)
        if not COMPILED:
            assert calls == {'sent': 1, 'received': 1}


class TestPeerEstablished:
    """Test Peer established() method"""

    def test_established_returns_true_when_established(self) -> None:
        """Test established() returns True in ESTABLISHED state"""
        peer = make_peer()
        peer.fsm.change(FSM.ESTABLISHED)

        assert peer.established() is True

    def test_established_returns_false_when_not_established(self) -> None:
        """Test established() returns False in other states"""
        peer = make_peer()

        assert peer.established() is False

        peer.fsm.change(FSM.ACTIVE)
        assert peer.established() is False

        peer.fsm.change(FSM.OPENCONFIRM)
        assert peer.established() is False


class TestPeerSocket:
    """Test Peer socket() method"""

    def test_socket_returns_fd_when_proto_exists(self) -> None:
        """Test socket() returns the connection's fd when a protocol exists"""
        peer = make_peer()
        proto = Protocol(peer)
        theirs = connect(proto)
        peer.proto = proto

        try:
            assert proto.connection is not None
            assert proto.connection.io is not None
            assert peer.socket() == proto.connection.io.fileno()
            assert peer.socket() >= 0
        finally:
            proto.close()
            theirs.close()

    def test_socket_returns_negative_when_no_proto(self) -> None:
        """Test socket() returns -1 when no protocol"""
        peer = make_peer()
        peer.proto = None

        assert peer.socket() == -1


class TestPeerReconfigure:
    """Test Peer reconfigure functionality"""

    def test_reconfigure_updates_neighbor(self) -> None:
        """Test reconfigure() updates neighbor reference"""
        peer = make_peer()
        new_neighbor = configured()

        peer.reconfigure(new_neighbor)

        # Neighbor reference updated immediately
        assert peer.neighbor is new_neighbor
        # _neighbor cleared when offline (issue #1126 fix)
        assert peer._neighbor is None

    def test_reconfigure_offline_updates_rib_directly(self) -> None:
        """Test reconfigure() updates RIB when peer is offline (issue #1126).

        When a neighbor is offline (not ESTABLISHED) during config reload,
        the RIB should be updated immediately since the main loop isn't
        running to process the _neighbor variable later.
        """
        before = configured(routes=('10.0.1.0/24 next-hop 192.0.2.1',))
        peer = make_peer(before)
        # Peer starts in IDLE (offline)
        assert peer.fsm == FSM.IDLE
        # the reloaded configuration: the old route replaced by a new one
        after = configured(routes=('10.0.2.0/24 next-hop 192.0.2.1',))
        after.previous = before
        # loading a configuration queues its routes: start from an empty queue
        after.rib.outgoing.reset()
        assert queued(after) == []

        peer.reconfigure(after)

        # RIB should be updated directly since peer is offline: the new route queued to
        # be announced, the one the configuration dropped queued to be withdrawn
        assert queued(after) == ['10.0.2.0/24']
        assert after.rib.outgoing.pending()
        # previous should be cleared
        assert after.previous is None
        # _neighbor should be cleared to prevent double-processing on reconnect
        assert peer._neighbor is None

    def test_reconfigure_online_defers_rib_update(self) -> None:
        """Test reconfigure() defers RIB update when peer is ESTABLISHED.

        When a neighbor is online (ESTABLISHED), the RIB update should be
        deferred to the main loop which will process _neighbor.
        """
        before = configured(routes=('10.0.1.0/24 next-hop 192.0.2.1',))
        peer = make_peer(before)
        peer.fsm.change(FSM.ESTABLISHED)
        after = configured(routes=('10.0.2.0/24 next-hop 192.0.2.1',))
        after.previous = before
        # loading a configuration queues its routes: start from an empty queue
        after.rib.outgoing.reset()

        peer.reconfigure(after)

        # RIB should NOT be updated directly - main loop will handle it
        assert queued(after) == []
        assert not after.rib.outgoing.pending()
        # _neighbor should be set for main loop to process
        assert peer._neighbor is after
        # previous should NOT be cleared (main loop will do it)
        assert after.previous is before

    def test_reconfigure_offline_no_rib(self) -> None:
        """Test reconfigure() handles a neighbour whose RIB is not enabled."""
        peer = make_peer()
        assert peer.fsm == FSM.IDLE

        # a Neighbor the configuration has not finished: its RIB is the disabled placeholder
        new_neighbor = Neighbor()
        assert not new_neighbor.rib.enabled
        new_neighbor.routes = configured(routes=('10.0.3.0/24 next-hop 192.0.2.1',)).routes

        # Should not raise
        peer.reconfigure(new_neighbor)
        assert peer.neighbor is new_neighbor
        assert queued(new_neighbor) == []

    def test_teardown_sets_code_and_restart(self) -> None:
        """Test teardown() sets correct code and restart flag"""
        peer = make_peer()
        notify = Notify(6, 6)
        peer.teardown(notify, restart=False)

        assert peer._teardown is notify
        assert peer._restart is False


class TestStats:
    """Test Stats class functionality"""

    def test_stats_initialization(self) -> None:
        """Test Stats initializes as dict"""
        stats = Stats()
        assert isinstance(stats, dict)

    def test_stats_tracks_changes(self) -> None:
        """Test Stats tracks changed items"""
        stats = Stats()
        stats['test'] = 1

        changes = list(stats.changed_statistics())
        assert len(changes) > 0

    def test_stats_changed_statistics_clears(self) -> None:
        """Test changed_statistics() clears changed set"""
        stats = Stats()
        stats['test'] = 1

        list(stats.changed_statistics())
        changes = list(stats.changed_statistics())

        # Should be empty after first call
        assert len(changes) == 0

    def test_stats_multiple_changes(self) -> None:
        """Test Stats tracks multiple changes"""
        stats = Stats()
        stats['test1'] = 1
        stats['test2'] = 2
        stats['test3'] = 3

        changes = list(stats.changed_statistics())
        assert len(changes) == 3


class TestPeerNegotiatedFamilies:
    """Test Peer negotiated_families() method"""

    def test_negotiated_families_with_proto(self) -> None:
        """Test negotiated_families() reports what the session negotiated"""
        # the configuration asks for one family, the session negotiated two
        peer = make_peer(configured('ipv4 unicast'))
        peer.proto = Protocol(peer)
        peer.proto.negotiated.families = [IPV4_UNICAST, IPV6_UNICAST]

        result = peer.negotiated_families()
        assert 'ipv4/unicast' in result
        assert 'ipv6/unicast' in result

    def test_negotiated_families_without_proto(self) -> None:
        """Test negotiated_families() when no protocol"""
        peer = make_peer(configured('ipv4 unicast'))
        peer.proto = None

        result = peer.negotiated_families()
        assert 'ipv4/unicast' in result

    def test_negotiated_families_single_family(self) -> None:
        """Test negotiated_families() with single family"""
        peer = make_peer(configured('ipv4 unicast'))
        peer.proto = None

        result = peer.negotiated_families()
        assert result == 'ipv4/unicast'

    def test_negotiated_families_multiple_families(self) -> None:
        """Test negotiated_families() with multiple families"""
        peer = make_peer(configured('ipv4 unicast', 'ipv6 unicast'))
        peer.proto = None

        result = peer.negotiated_families()
        assert result == '[ ipv4/unicast ipv6/unicast ]'


class TestPeerRun:
    """Test Peer run() method"""

    @pytest.mark.asyncio
    async def test_run_checks_broken_process(self) -> None:
        """Test run() stops the peer when an API process is broken"""
        neighbor = configured()
        peer = make_peer(neighbor)
        processes = peer.reactor.processes
        # what Processes records of a helper which died and could not be respawned
        processes._configuration['helper'] = {}
        processes._broken.append('helper')
        processes.terminate_on_error = False
        assert processes.broken(neighbor)

        await asyncio.wait_for(peer.run(), timeout=5)

        # Should stop peer when process is broken
        assert peer._restart is False
        assert peer._teardown is not None
        assert neighbor.rib.name not in RIB._cache

    @pytest.mark.asyncio
    async def test_run_without_a_broken_process_does_not_stop(self) -> None:
        """The other side of the test above: the stop is the broken helper's doing"""
        peer = make_peer()
        assert not peer.reactor.processes.broken(peer.neighbor)
        # a peer told not to restart leaves run() at once, without being stopped
        peer._restart = False

        await asyncio.wait_for(peer.run(), timeout=5)

        assert peer._teardown is None


class TestPeerRemoveShutdown:
    """Test Peer remove() and shutdown() methods"""

    def test_remove_stops_peer(self) -> None:
        """Test remove() stops peer"""
        peer = make_peer()
        peer.remove()

        assert peer._restart is False
        assert peer.fsm == FSM.IDLE

    def test_shutdown_stops_peer(self) -> None:
        """Test shutdown() stops peer"""
        peer = make_peer()
        peer.shutdown()

        assert peer._restart is False
        assert peer.fsm == FSM.IDLE


class TestPeerResend:
    """Test Peer resend() method"""

    def test_resend_calls_rib_resend(self) -> None:
        """Test resend() asks the RIB to resend the family, as an enhanced refresh"""
        neighbor = configured('ipv4 unicast', 'ipv6 unicast')
        peer = make_peer(neighbor)
        neighbor.rib.outgoing.reset()

        peer.resend(True, family=IPV4_UNICAST)

        # the enhanced refresh is marked for the one family asked for, not the other
        assert neighbor.rib.outgoing._refresh_families == {IPV4_UNICAST}

    def test_resend_resets_delay(self) -> None:
        """Test resend() resets delay"""
        peer = make_peer()
        peer._delay.increase()

        peer.resend(False)

        # Delay should be reset (_next should be 0)
        assert peer._delay._next == 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
