#!/usr/bin/env python3
# encoding: utf-8
"""test_peer_state_machine.py

Comprehensive tests for BGP Peer State Machine implementation.
Tests state transitions, timers, collision detection, and error recovery.

Created: 2025-11-08
"""

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
from exabgp.bgp.message import Scheduling  # noqa: E402
from exabgp.reactor.peer import Peer, Stats  # noqa: E402


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


class TestPeerInitialization:
    """Test Peer object initialization"""

    def test_peer_init_basic(self) -> None:
        """Test basic Peer initialization"""
        neighbor = Mock()
        neighbor.uid = '1'
        neighbor.api = {'neighbor-changes': False, 'fsm': False}
        neighbor.rib = Mock()
        reactor = Mock()

        peer = Peer(neighbor, reactor)

        assert peer.neighbor is neighbor
        assert peer.reactor is reactor
        assert peer.fsm == FSM.IDLE
        assert peer.proto is None
        assert peer._restart is True
        assert peer._restarted is True

    def test_peer_init_stats(self) -> None:
        """Test Peer initialization creates stats"""
        neighbor = Mock()
        neighbor.uid = '1'
        neighbor.api = {'neighbor-changes': False, 'fsm': False}
        reactor = Mock()

        peer = Peer(neighbor, reactor)

        assert 'fsm' in peer.stats
        assert 'creation' in peer.stats
        assert 'reset' in peer.stats
        assert 'complete' in peer.stats
        assert 'up' in peer.stats
        assert 'down' in peer.stats

    def test_peer_init_message_counters(self) -> None:
        """Test Peer initialization creates message counters"""
        neighbor = Mock()
        neighbor.uid = '1'
        neighbor.api = {'neighbor-changes': False, 'fsm': False}
        reactor = Mock()

        peer = Peer(neighbor, reactor)

        assert peer.stats['receive-open'] == 0
        assert peer.stats['send-open'] == 0
        assert peer.stats['receive-keepalive'] == 0
        assert peer.stats['send-keepalive'] == 0
        assert peer.stats['receive-update'] == 0
        assert peer.stats['send-update'] == 0
        assert peer.stats['receive-notification'] == 0
        assert peer.stats['send-notification'] == 0

    def test_peer_id_generation(self) -> None:
        """Test Peer generates unique ID"""
        neighbor = Mock()
        neighbor.uid = '123'
        neighbor.api = {'neighbor-changes': False, 'fsm': False}
        reactor = Mock()

        peer = Peer(neighbor, reactor)

        assert peer.id() == 'peer-123'


class TestPeerStateTransitions:
    """Test Peer state transitions through FSM"""

    def test_peer_starts_in_idle(self) -> None:
        """Test Peer starts in IDLE state"""
        neighbor = Mock()
        neighbor.uid = '1'
        neighbor.api = {'neighbor-changes': False, 'fsm': False}
        reactor = Mock()

        peer = Peer(neighbor, reactor)

        assert peer.fsm == FSM.IDLE

    def test_peer_close_transitions_to_idle(self) -> None:
        """Test _close transitions Peer to IDLE"""
        neighbor = Mock()
        neighbor.uid = '1'
        neighbor.api = {'neighbor-changes': False, 'fsm': False}
        neighbor.ephemeral = False
        reactor = Mock()

        peer = Peer(neighbor, reactor)
        peer.fsm.change(FSM.ESTABLISHED)

        peer._close('test close')

        assert peer.fsm == FSM.IDLE
        assert peer.proto is None

    def test_peer_reset_clears_state(self) -> None:
        """Test _reset clears peer state"""
        neighbor = Mock()
        neighbor.uid = '1'
        neighbor.api = {'neighbor-changes': False, 'fsm': False}
        neighbor.ephemeral = False
        neighbor.reset_rib = Mock()
        reactor = Mock()

        peer = Peer(neighbor, reactor)
        peer.fsm.change(FSM.ESTABLISHED)

        peer._reset('test reset')

        assert peer.fsm == FSM.IDLE
        assert not peer.fsm_runner.running
        assert not peer.fsm_runner.terminated
        assert peer._teardown is None
        neighbor.reset_rib.assert_called_once()

    def test_peer_stop_sets_flags(self) -> None:
        """Test stop() sets correct flags"""
        neighbor = Mock()
        neighbor.uid = '1'
        neighbor.api = {'neighbor-changes': False, 'fsm': False}
        neighbor.rib = Mock()
        neighbor.rib.uncache = Mock()
        reactor = Mock()

        peer = Peer(neighbor, reactor)

        peer.stop()

        assert peer._restart is False
        assert peer._restarted is False
        assert peer.fsm == FSM.IDLE
        neighbor.rib.uncache.assert_called_once()

    def test_peer_reestablish_sets_teardown(self) -> None:
        """Test reestablish() sets teardown flag"""
        neighbor = Mock()
        neighbor.uid = '1'
        neighbor.api = {'neighbor-changes': False, 'fsm': False}
        reactor = Mock()

        peer = Peer(neighbor, reactor)

        peer.reestablish()

        assert peer._teardown == 3
        assert peer._restart is True
        assert peer._restarted is True


class TestPeerCollisionDetection:
    """Test Peer collision detection logic"""

    def test_collision_reject_when_established(self) -> None:
        """Test collision detection rejects connection when established"""
        neighbor = Mock()
        neighbor.uid = '1'
        neighbor.api = {'neighbor-changes': False, 'fsm': False}
        reactor = Mock()

        peer = Peer(neighbor, reactor)
        peer.fsm.change(FSM.ESTABLISHED)

        connection = Mock()
        connection.name = Mock(return_value='test-connection')
        connection.notification = Mock(return_value='notification')

        result = peer.handle_connection(connection)

        assert result is not None
        connection.notification.assert_called_once_with(6, 7, b'could not accept the connection, already established')

    def test_collision_detection_openconfirm_higher_router_id(self) -> None:
        """Test collision detection in OPENCONFIRM with higher local router-id"""
        neighbor = Mock()
        neighbor.uid = '1'
        neighbor.api = {'neighbor-changes': False, 'fsm': False}
        # Neighbor now uses session for connection-related config
        neighbor.session = Mock()
        neighbor.session.router_id = Mock(pack_ip=Mock(return_value=b'\x02\x02\x02\x02'))
        reactor = Mock()

        peer = Peer(neighbor, reactor)
        peer.fsm.change(FSM.OPENCONFIRM)

        # Create mock protocol with negotiated_in OPEN
        peer.proto = Mock()
        peer.proto.negotiated = Mock()
        peer.proto.negotiated.received_open = Mock()
        peer.proto.negotiated.received_open.router_id = Mock(pack_ip=Mock(return_value=b'\x01\x01\x01\x01'))

        connection = Mock()
        connection.name = Mock(return_value='test-connection')
        connection.notification = Mock(return_value='notification')

        result = peer.handle_connection(connection)

        # Should reject incoming connection (local ID is higher)
        assert result is not None
        connection.notification.assert_called_once()

    def test_collision_detection_openconfirm_lower_router_id(self) -> None:
        """Test collision detection in OPENCONFIRM with lower local router-id"""
        neighbor = Mock()
        neighbor.uid = '1'
        neighbor.api = {'neighbor-changes': False, 'fsm': False}
        # Neighbor now uses session for connection-related config
        neighbor.session = Mock()
        neighbor.session.router_id = Mock(pack_ip=Mock(return_value=b'\x01\x01\x01\x01'))
        reactor = Mock()

        peer = Peer(neighbor, reactor)
        peer.fsm.change(FSM.OPENCONFIRM)

        # Create mock protocol with negotiated_in OPEN
        peer.proto = Mock()
        peer.proto.negotiated = Mock()
        peer.proto.negotiated.received_open = Mock()
        peer.proto.negotiated.received_open.router_id = Mock(pack_ip=Mock(return_value=b'\x02\x02\x02\x02'))
        peer.proto.close = Mock()

        from exabgp.reactor.protocol import Protocol

        connection = Mock()
        connection.name = Mock(return_value='test-connection')

        with patch.object(Protocol, '__init__', return_value=None):
            with patch.object(Protocol, 'accept', return_value=Mock()):
                result = peer.handle_connection(connection)

        # Should accept incoming connection (local ID is lower)
        assert result is None
        assert peer.proto is not None

    def test_collision_accept_replaces_proto(self) -> None:
        """Test accepting collision replaces existing protocol"""
        neighbor = Mock()
        neighbor.uid = '1'
        neighbor.api = {'neighbor-changes': False, 'fsm': False}
        reactor = Mock()

        peer = Peer(neighbor, reactor)
        peer.fsm.change(FSM.ACTIVE)

        old_proto = Mock()
        peer.proto = old_proto

        from exabgp.reactor.protocol import Protocol

        connection = Mock()
        connection.name = Mock(return_value='test-connection')

        with patch.object(Protocol, '__init__', return_value=None):
            with patch.object(Protocol, 'accept', return_value=Mock()):
                result = peer.handle_connection(connection)

        # Should accept connection and replace proto
        assert result is None
        assert not peer.fsm_runner.running


class TestPeerTimers:
    """Test Peer timer functionality"""

    def test_receive_timer_initialized(self) -> None:
        """Test receive timer is initialized after OPENCONFIRM"""
        neighbor = Mock()
        neighbor.uid = '1'
        neighbor.api = {'neighbor-changes': False, 'fsm': False}
        reactor = Mock()

        peer = Peer(neighbor, reactor)

        assert peer.recv_timer is None

    def test_peer_delay_increase_on_close(self) -> None:
        """Test delay increases on connection close"""
        neighbor = Mock()
        neighbor.uid = '1'
        neighbor.api = {'neighbor-changes': False, 'fsm': False}
        neighbor.ephemeral = False
        reactor = Mock()

        peer = Peer(neighbor, reactor)
        initial_next = peer._delay._next

        peer._close('test')

        # Delay should increase after close (tracked by _next value)
        assert peer._delay._next > initial_next

    def test_peer_delay_reset_on_reestablish(self) -> None:
        """Test delay resets on reestablish"""
        neighbor = Mock()
        neighbor.uid = '1'
        neighbor.api = {'neighbor-changes': False, 'fsm': False}
        reactor = Mock()

        peer = Peer(neighbor, reactor)
        peer._delay.increase()
        peer._delay.increase()

        peer.reestablish()

        # Delay should be reset (_next should be 0)
        assert peer._delay._next == 0

    def test_peer_delay_reset_on_teardown(self) -> None:
        """Test delay resets on teardown"""
        neighbor = Mock()
        neighbor.uid = '1'
        neighbor.api = {'neighbor-changes': False, 'fsm': False}
        reactor = Mock()

        peer = Peer(neighbor, reactor)
        peer._delay.increase()

        peer.teardown(3, restart=True)

        # Delay should be reset (_next should be 0)
        assert peer._delay._next == 0


class TestPeerErrorRecovery:
    """Test Peer error recovery mechanisms"""

    def test_peer_close_on_error_transitions_to_idle(self) -> None:
        """Test _close transitions peer to IDLE on error"""
        neighbor = Mock()
        neighbor.uid = '1'
        neighbor.api = {'neighbor-changes': False, 'fsm': False}
        neighbor.ephemeral = False
        reactor = Mock()

        peer = Peer(neighbor, reactor)
        peer.fsm.change(FSM.ESTABLISHED)

        peer._close('test error', 'network error')

        # Should transition to IDLE after error
        assert peer.fsm == FSM.IDLE

    def test_peer_reset_on_error_clears_state(self) -> None:
        """Test _reset clears peer state on error"""
        neighbor = Mock()
        neighbor.uid = '1'
        neighbor.api = {'neighbor-changes': False, 'fsm': False}
        neighbor.ephemeral = False
        neighbor.reset_rib = Mock()
        reactor = Mock()

        peer = Peer(neighbor, reactor)
        peer.fsm.change(FSM.ESTABLISHED)
        peer._teardown = 6

        peer._reset('notification received', 'error')

        # Should reset state
        assert peer.fsm == FSM.IDLE
        assert peer._teardown is None
        neighbor.reset_rib.assert_called_once()

    def test_peer_handles_network_error_state(self) -> None:
        """Test Peer error handling transitions to IDLE"""
        neighbor = Mock()
        neighbor.uid = '1'
        neighbor.api = {'neighbor-changes': False, 'fsm': False}
        neighbor.ephemeral = False
        neighbor.reset_rib = Mock()
        reactor = Mock()

        peer = Peer(neighbor, reactor)
        peer.fsm.change(FSM.OPENCONFIRM)

        # Simulate error by calling _reset
        peer._reset('network error')

        assert peer.fsm == FSM.IDLE

    def test_peer_error_increases_delay(self) -> None:
        """Test error increases backoff delay"""
        neighbor = Mock()
        neighbor.uid = '1'
        neighbor.api = {'neighbor-changes': False, 'fsm': False}
        neighbor.ephemeral = False
        reactor = Mock()

        peer = Peer(neighbor, reactor)
        initial_next = peer._delay._next

        # Simulate error
        peer._close('test error')

        # Delay should increase
        assert peer._delay._next > initial_next

    def test_peer_clears_proto_on_error(self) -> None:
        """Test Peer clears protocol on error"""
        neighbor = Mock()
        neighbor.uid = '1'
        neighbor.api = {'neighbor-changes': False, 'fsm': False}
        neighbor.ephemeral = False
        reactor = Mock()

        peer = Peer(neighbor, reactor)
        peer.proto = Mock()
        peer.proto.close = Mock()

        peer._close('test error')

        # Protocol should be cleared
        assert peer.proto is None


class TestPeerConnectionAttempts:
    """Test Peer connection attempt limiting"""

    def test_can_reconnect_unlimited(self) -> None:
        """Test can_reconnect with unlimited attempts"""
        neighbor = Mock()
        neighbor.uid = '1'
        neighbor.api = {'neighbor-changes': False, 'fsm': False}
        reactor = Mock()

        with patch('exabgp.reactor.peer.peer.getenv') as mock_env:
            mock_env.return_value.tcp.attempts = 0  # unlimited
            peer = Peer(neighbor, reactor)

        assert peer.can_reconnect() is True
        peer.connection_attempts = 1000
        assert peer.can_reconnect() is True

    def test_can_reconnect_limited(self) -> None:
        """Test can_reconnect with limited attempts"""
        neighbor = Mock()
        neighbor.uid = '1'
        neighbor.api = {'neighbor-changes': False, 'fsm': False}
        reactor = Mock()

        with patch('exabgp.reactor.peer.peer.getenv') as mock_env:
            mock_env.return_value.tcp.attempts = 3
            peer = Peer(neighbor, reactor)

        assert peer.can_reconnect() is True
        peer.connection_attempts = 2
        assert peer.can_reconnect() is True
        peer.connection_attempts = 3
        assert peer.can_reconnect() is False
        peer.connection_attempts = 4
        assert peer.can_reconnect() is False

    def test_connection_attempt_counting(self) -> None:
        """Test connection attempts are tracked"""
        neighbor = Mock()
        neighbor.uid = '1'
        neighbor.api = {'neighbor-changes': False, 'fsm': False}
        reactor = Mock()

        with patch('exabgp.reactor.peer.peer.getenv') as mock_env:
            mock_env.return_value.tcp.attempts = 3
            peer = Peer(neighbor, reactor)

        # Initially no attempts
        assert peer.connection_attempts == 0

        # Simulate attempts
        peer.connection_attempts = 2
        assert peer.can_reconnect() is True

        peer.connection_attempts = 3
        assert peer.can_reconnect() is False


class TestPeerEstablished:
    """Test Peer established() method"""

    def test_established_returns_true_when_established(self) -> None:
        """Test established() returns True in ESTABLISHED state"""
        neighbor = Mock()
        neighbor.uid = '1'
        neighbor.api = {'neighbor-changes': False, 'fsm': False}
        reactor = Mock()

        peer = Peer(neighbor, reactor)
        peer.fsm.change(FSM.ESTABLISHED)

        assert peer.established() is True

    def test_established_returns_false_when_not_established(self) -> None:
        """Test established() returns False in other states"""
        neighbor = Mock()
        neighbor.uid = '1'
        neighbor.api = {'neighbor-changes': False, 'fsm': False}
        reactor = Mock()

        peer = Peer(neighbor, reactor)

        assert peer.established() is False

        peer.fsm.change(FSM.ACTIVE)
        assert peer.established() is False

        peer.fsm.change(FSM.OPENCONFIRM)
        assert peer.established() is False


class TestPeerSocket:
    """Test Peer socket() method"""

    def test_socket_returns_fd_when_proto_exists(self) -> None:
        """Test socket() returns fd when protocol exists"""
        neighbor = Mock()
        neighbor.uid = '1'
        neighbor.api = {'neighbor-changes': False, 'fsm': False}
        reactor = Mock()

        peer = Peer(neighbor, reactor)
        peer.proto = Mock()
        peer.proto.fd = Mock(return_value=42)

        assert peer.socket() == 42

    def test_socket_returns_negative_when_no_proto(self) -> None:
        """Test socket() returns -1 when no protocol"""
        neighbor = Mock()
        neighbor.uid = '1'
        neighbor.api = {'neighbor-changes': False, 'fsm': False}
        reactor = Mock()

        peer = Peer(neighbor, reactor)
        peer.proto = None

        assert peer.socket() == -1


class TestPeerReconfigure:
    """Test Peer reconfigure functionality"""

    def test_reconfigure_updates_neighbor(self) -> None:
        """Test reconfigure() updates neighbor reference"""
        neighbor = Mock()
        neighbor.uid = '1'
        neighbor.api = {'neighbor-changes': False, 'fsm': False}
        reactor = Mock()

        new_neighbor = Mock()
        new_neighbor.uid = '2'

        peer = Peer(neighbor, reactor)
        peer.reconfigure(new_neighbor)

        assert peer._neighbor is new_neighbor

    def test_teardown_sets_code_and_restart(self) -> None:
        """Test teardown() sets correct code and restart flag"""
        neighbor = Mock()
        neighbor.uid = '1'
        neighbor.api = {'neighbor-changes': False, 'fsm': False}
        reactor = Mock()

        peer = Peer(neighbor, reactor)
        peer.teardown(6, restart=False)

        assert peer._teardown == 6
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
        """Test negotiated_families() when protocol exists"""
        neighbor = Mock()
        neighbor.uid = '1'
        neighbor.api = {'neighbor-changes': False, 'fsm': False}
        reactor = Mock()

        peer = Peer(neighbor, reactor)
        peer.proto = Mock()
        peer.proto.negotiated = Mock()
        peer.proto.negotiated.families = [(1, 1), (2, 1)]

        result = peer.negotiated_families()
        assert '1/1' in result
        assert '2/1' in result

    def test_negotiated_families_without_proto(self) -> None:
        """Test negotiated_families() when no protocol"""
        neighbor = Mock()
        neighbor.uid = '1'
        neighbor.api = {'neighbor-changes': False, 'fsm': False}
        neighbor.families = Mock(return_value=[(1, 1)])
        reactor = Mock()

        peer = Peer(neighbor, reactor)
        peer.proto = None

        result = peer.negotiated_families()
        assert '1/1' in result

    def test_negotiated_families_single_family(self) -> None:
        """Test negotiated_families() with single family"""
        neighbor = Mock()
        neighbor.uid = '1'
        neighbor.api = {'neighbor-changes': False, 'fsm': False}
        neighbor.families = Mock(return_value=[(1, 1)])
        reactor = Mock()

        peer = Peer(neighbor, reactor)
        peer.proto = None

        result = peer.negotiated_families()
        assert result == '1/1'

    def test_negotiated_families_multiple_families(self) -> None:
        """Test negotiated_families() with multiple families"""
        neighbor = Mock()
        neighbor.uid = '1'
        neighbor.api = {'neighbor-changes': False, 'fsm': False}
        neighbor.families = Mock(return_value=[(1, 1), (2, 1)])
        reactor = Mock()

        peer = Peer(neighbor, reactor)
        peer.proto = None

        result = peer.negotiated_families()
        assert '[' in result
        assert ']' in result


class TestSchedulingConstants:
    """Test Scheduling enum constants"""

    def test_scheduling_constants_defined(self) -> None:
        """Test Scheduling constants are defined"""
        # Values are: MESSAGE=0, NOW=1, LATER=2, CLOSE=3
        assert Scheduling.MESSAGE == 0x00
        assert Scheduling.NOW == 0x01
        assert Scheduling.LATER == 0x02
        assert Scheduling.CLOSE == 0x03

    def test_scheduling_all_values(self) -> None:
        """Test Scheduling contains all expected values"""
        assert Scheduling.MESSAGE in list(Scheduling)
        assert Scheduling.CLOSE in list(Scheduling)
        assert Scheduling.LATER in list(Scheduling)
        assert Scheduling.NOW in list(Scheduling)
        assert len(list(Scheduling)) == 4


class TestPeerRun:
    """Test Peer run() method"""

    @pytest.mark.asyncio
    async def test_run_checks_broken_process(self) -> None:
        """Test run() checks for broken process"""
        neighbor = Mock()
        neighbor.uid = '1'
        neighbor.api = {'neighbor-changes': False, 'fsm': False}
        neighbor.rib = Mock()
        neighbor.rib.uncache = Mock()
        reactor = Mock()
        reactor.processes = Mock()
        reactor.processes.broken = Mock(return_value=True)
        reactor.processes.terminate_on_error = False

        peer = Peer(neighbor, reactor)

        await peer.run()

        # Should stop peer when process is broken
        assert peer._restart is False
        reactor.processes.broken.assert_called_once_with(neighbor)


class TestPeerRemoveShutdown:
    """Test Peer remove() and shutdown() methods"""

    def test_remove_stops_peer(self) -> None:
        """Test remove() stops peer"""
        neighbor = Mock()
        neighbor.uid = '1'
        neighbor.api = {'neighbor-changes': False, 'fsm': False}
        neighbor.rib = Mock()
        neighbor.rib.uncache = Mock()
        reactor = Mock()

        peer = Peer(neighbor, reactor)
        peer.remove()

        assert peer._restart is False
        assert peer.fsm == FSM.IDLE

    def test_shutdown_stops_peer(self) -> None:
        """Test shutdown() stops peer"""
        neighbor = Mock()
        neighbor.uid = '1'
        neighbor.api = {'neighbor-changes': False, 'fsm': False}
        neighbor.rib = Mock()
        neighbor.rib.uncache = Mock()
        reactor = Mock()

        peer = Peer(neighbor, reactor)
        peer.shutdown()

        assert peer._restart is False
        assert peer.fsm == FSM.IDLE


class TestPeerResend:
    """Test Peer resend() method"""

    def test_resend_calls_rib_resend(self) -> None:
        """Test resend() calls RIB resend"""
        neighbor = Mock()
        neighbor.uid = '1'
        neighbor.api = {'neighbor-changes': False, 'fsm': False}
        neighbor.rib = Mock()
        neighbor.rib.outgoing = Mock()
        neighbor.rib.outgoing.resend = Mock()
        reactor = Mock()

        peer = Peer(neighbor, reactor)
        peer.resend(True, family=(1, 1))

        neighbor.rib.outgoing.resend.assert_called_once_with(True, (1, 1))

    def test_resend_resets_delay(self) -> None:
        """Test resend() resets delay"""
        neighbor = Mock()
        neighbor.uid = '1'
        neighbor.api = {'neighbor-changes': False, 'fsm': False}
        neighbor.rib = Mock()
        neighbor.rib.outgoing = Mock()
        neighbor.rib.outgoing.resend = Mock()
        reactor = Mock()

        peer = Peer(neighbor, reactor)
        peer._delay.increase()

        peer.resend(False)

        # Delay should be reset (_next should be 0)
        assert peer._delay._next == 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
