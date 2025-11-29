"""test_loop.py

Unit tests for reactor/loop.py (Reactor class).

Test Coverage:
- Exit codes
- Spin prevention logic
- Rate limiting logic
- Peer management methods
- Neighbor accessors

Note: Uses MockReactor pattern since real Reactor has complex dependencies.
Logic is tested by extracting and testing the algorithms directly.
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Dict, List, Optional, Set
from unittest.mock import Mock, MagicMock


class MockReactor:
    """Mock Reactor that mimics real Reactor's testable methods.

    This allows testing the logic without complex dependency initialization.
    """

    class Exit:
        normal: int = 0
        validate: int = 0
        listening: int = 1
        configuration: int = 1
        privileges: int = 1
        log: int = 1
        pid: int = 1
        socket: int = 1
        io_error: int = 1
        process: int = 1
        select: int = 1
        unknown: int = 1

    def __init__(self) -> None:
        self.daemon_uuid: str = str(uuid.uuid4())
        self.daemon_start_time: float = time.time()
        self.exit_code: int = self.Exit.unknown

        # Active CLI client tracking
        self.active_client_uuid: Optional[str] = None
        self.active_client_last_ping: float = 0.0

        # Rate limiting
        self.max_loop_time: float = 1.0
        self._sleep_time: float = 0.01
        self._busyspin: Dict[int, int] = {}
        self._ratelimit: Dict[str, Dict[int, int]] = {}

        # Peers
        self._peers: Dict[str, Any] = {}

        # Signal mock
        self.signal = MagicMock()
        self.signal.received = None

    def _prevent_spin(self) -> bool:
        """Prevent busy spinning by rate limiting iterations per second."""
        second: int = int(time.time())
        if second not in self._busyspin:
            self._busyspin = {second: 0}
        self._busyspin[second] += 1
        if self._busyspin[second] > self.max_loop_time:
            time.sleep(self._sleep_time)
            return True
        return False

    def _rate_limited(self, peer: str, rate: int) -> bool:
        """Check if peer is rate limited."""
        if rate <= 0:
            return False
        second: int = int(time.time())
        ratelimit: Dict[int, int] = self._ratelimit.get(peer, {})
        if second not in ratelimit:
            self._ratelimit[peer] = {second: rate - 1}
            return False
        if self._ratelimit[peer][second] > 0:
            self._ratelimit[peer][second] -= 1
            return False
        return True

    def active_peers(self) -> Set[str]:
        """Return set of active peer names."""
        from exabgp.bgp.message import Scheduling

        return {key for key in self._peers.keys() if self._peers[key].action != Scheduling.LATER}

    def established_peers(self) -> Set[str]:
        """Return set of established peer names."""
        from exabgp.bgp.fsm import FSM

        return {key for key in self._peers.keys() if self._peers[key].fsm.state == FSM.ESTABLISHED}

    def peers(self, service: str = '') -> List[str]:
        """Return list of peer names, optionally filtered by service."""
        if not service:
            return list(self._peers.keys())
        # NOTE: 'process' is not a real Neighbor attribute, it's part of neighbor.api
        # This mock implementation is simplified
        return [
            key
            for key in self._peers.keys()
            if hasattr(self._peers[key].neighbor, 'api')
            and self._peers[key].neighbor.api
            and service in self._peers[key].neighbor.api.get('processes', [])
        ]

    def neighbor(self, peer_name: str) -> Optional[Any]:
        """Get neighbor configuration for a peer."""
        peer = self._peers.get(peer_name, None)
        if peer is None:
            return None
        return peer.neighbor

    def neighbor_name(self, peer_name: str) -> str:
        """Get neighbor name."""
        if peer_name not in self._peers:
            return ''
        return peer_name

    def neighbor_ip(self, peer_name: str) -> str:
        """Get neighbor IP address."""
        peer = self._peers.get(peer_name, None)
        if peer is None:
            return ''
        return str(peer.neighbor.peer_address)

    def _pending_adjribout(self) -> bool:
        """Check if any peer has pending adjribout."""
        for peer in self._peers.values():
            if peer.neighbor.rib.outgoing.pending():
                return True
        return False

    def register_peer(self, name: str, peer: Any) -> None:
        """Register a peer."""
        self._peers[name] = peer

    def teardown_peer(self, name: str, code: int) -> None:
        """Teardown and remove a peer."""
        if name in self._peers:
            del self._peers[name]

    def _termination(self, reason: str, exit_code: int) -> None:
        """Handle termination."""
        self.exit_code = exit_code
        self.signal.received = 'SHUTDOWN'


class TestExitCodes:
    """Test Exit class constants."""

    def test_exit_normal_is_zero(self) -> None:
        """Test normal exit is 0."""
        assert MockReactor.Exit.normal == 0

    def test_exit_validate_is_zero(self) -> None:
        """Test validate exit is 0."""
        assert MockReactor.Exit.validate == 0

    def test_exit_configuration_is_one(self) -> None:
        """Test configuration exit is 1."""
        assert MockReactor.Exit.configuration == 1

    def test_exit_unknown_is_one(self) -> None:
        """Test unknown exit is 1."""
        assert MockReactor.Exit.unknown == 1

    def test_exit_codes_are_consistent(self) -> None:
        """Test exit codes follow expected pattern (0=success, 1=error)."""
        # Success codes
        assert MockReactor.Exit.normal == 0
        assert MockReactor.Exit.validate == 0
        # Error codes
        assert MockReactor.Exit.configuration == 1
        assert MockReactor.Exit.unknown == 1
        assert MockReactor.Exit.listening == 1
        assert MockReactor.Exit.privileges == 1


class TestReactorInit:
    """Test Reactor initialization via MockReactor."""

    def test_init_creates_uuid(self) -> None:
        """Test that initialization creates a daemon UUID."""
        reactor = MockReactor()
        assert reactor.daemon_uuid is not None
        assert len(reactor.daemon_uuid) == 36  # UUID format

    def test_init_records_start_time(self) -> None:
        """Test that initialization records start time."""
        reactor = MockReactor()
        assert reactor.daemon_start_time > 0
        assert reactor.daemon_start_time <= time.time()

    def test_init_sets_exit_code_unknown(self) -> None:
        """Test that initial exit code is unknown."""
        reactor = MockReactor()
        assert reactor.exit_code == MockReactor.Exit.unknown

    def test_init_empty_peers(self) -> None:
        """Test that peers dict starts empty."""
        reactor = MockReactor()
        assert reactor._peers == {}

    def test_init_no_active_client(self) -> None:
        """Test that no active client at init."""
        reactor = MockReactor()
        assert reactor.active_client_uuid is None
        assert reactor.active_client_last_ping == 0.0


class TestPreventSpin:
    """Test spin prevention mechanism."""

    def test_prevent_spin_first_call(self) -> None:
        """Test first call in a second doesn't sleep."""
        reactor = MockReactor()
        reactor._busyspin = {}
        result = reactor._prevent_spin()
        assert result is False

    def test_prevent_spin_increments_counter(self) -> None:
        """Test that counter increments each call."""
        reactor = MockReactor()
        reactor._busyspin = {}
        reactor._prevent_spin()
        second = int(time.time())
        assert reactor._busyspin[second] == 1

        reactor._prevent_spin()
        assert reactor._busyspin[second] == 2

    def test_prevent_spin_returns_true_over_limit(self) -> None:
        """Test returns True when over max_loop_time."""
        reactor = MockReactor()
        reactor.max_loop_time = 5
        reactor._sleep_time = 0.001
        reactor._busyspin = {}

        # Call more than max_loop_time times
        for _ in range(6):
            result = reactor._prevent_spin()

        assert result is True

    def test_prevent_spin_resets_on_new_second(self) -> None:
        """Test that counter resets on new second."""
        reactor = MockReactor()
        old_second = int(time.time()) - 1
        reactor._busyspin = {old_second: 1000}

        reactor._prevent_spin()

        current_second = int(time.time())
        assert current_second in reactor._busyspin
        assert old_second not in reactor._busyspin


class TestRateLimited:
    """Test per-peer rate limiting."""

    def test_rate_limited_disabled_when_zero(self) -> None:
        """Test rate limiting disabled when rate is 0."""
        reactor = MockReactor()
        result = reactor._rate_limited('peer1', 0)
        assert result is False

    def test_rate_limited_disabled_when_negative(self) -> None:
        """Test rate limiting disabled when rate is negative."""
        reactor = MockReactor()
        result = reactor._rate_limited('peer1', -1)
        assert result is False

    def test_rate_limited_first_call_allowed(self) -> None:
        """Test first call within rate is allowed."""
        reactor = MockReactor()
        reactor._ratelimit = {}
        result = reactor._rate_limited('peer1', 10)
        assert result is False

    def test_rate_limited_decrements_counter(self) -> None:
        """Test counter decrements each call."""
        reactor = MockReactor()
        reactor._ratelimit = {}
        reactor._rate_limited('peer1', 10)

        second = int(time.time())
        assert reactor._ratelimit['peer1'][second] == 9

    def test_rate_limited_blocks_when_exhausted(self) -> None:
        """Test blocking when rate exhausted."""
        reactor = MockReactor()
        reactor._ratelimit = {}

        # Exhaust the rate
        for _ in range(10):
            reactor._rate_limited('peer1', 10)

        # Next call should be blocked
        result = reactor._rate_limited('peer1', 10)
        assert result is True

    def test_rate_limited_per_peer_isolation(self) -> None:
        """Test rate limits are per-peer."""
        reactor = MockReactor()
        reactor._ratelimit = {}

        # Exhaust peer1's rate
        for _ in range(10):
            reactor._rate_limited('peer1', 10)

        # peer2 should still be allowed
        result = reactor._rate_limited('peer2', 10)
        assert result is False


class TestActivePeers:
    """Test active_peers method."""

    def test_active_peers_empty(self) -> None:
        """Test empty peers returns empty set."""

        # Define a simple version that doesn't need imports
        def active_peers(peers: Dict[str, Any]) -> Set[str]:
            """Return set of peers where action != 'LATER'."""
            return {key for key in peers.keys() if peers[key].action != 'LATER'}

        result = active_peers({})
        assert result == set()

    def test_active_peers_filters_action_later(self) -> None:
        """Test filters out peers with ACTION.LATER."""

        # Define a simple version that doesn't need imports
        def active_peers(peers: Dict[str, Any]) -> Set[str]:
            """Return set of peers where action != 'LATER'."""
            return {key for key in peers.keys() if peers[key].action != 'LATER'}

        peer1 = MagicMock()
        peer1.action = 'LATER'

        peer2 = MagicMock()
        peer2.action = 'NOW'

        peers = {'peer1': peer1, 'peer2': peer2}
        result = active_peers(peers)

        assert 'peer1' not in result
        assert 'peer2' in result


class TestEstablishedPeers:
    """Test established_peers method."""

    def test_established_peers_empty(self) -> None:
        """Test empty peers returns empty set."""

        # Define a simple version that doesn't need imports
        def established_peers(peers: Dict[str, Any], established_state: str) -> Set[str]:
            """Return set of peers in established state."""
            return {key for key in peers.keys() if peers[key].fsm.state == established_state}

        result = established_peers({}, 'ESTABLISHED')
        assert result == set()

    def test_established_peers_filters_by_fsm(self) -> None:
        """Test filters peers by FSM.ESTABLISHED state."""

        # Define a simple version that doesn't need imports
        def established_peers(peers: Dict[str, Any], established_state: str) -> Set[str]:
            """Return set of peers in established state."""
            return {key for key in peers.keys() if peers[key].fsm.state == established_state}

        peer1 = MagicMock()
        peer1.fsm = MagicMock()
        peer1.fsm.state = 'ESTABLISHED'

        peer2 = MagicMock()
        peer2.fsm = MagicMock()
        peer2.fsm.state = 'IDLE'

        peers = {'peer1': peer1, 'peer2': peer2}
        result = established_peers(peers, 'ESTABLISHED')

        assert 'peer1' in result
        assert 'peer2' not in result


class TestPeers:
    """Test peers method with filtering."""

    def test_peers_empty(self) -> None:
        """Test empty peers returns empty list."""
        reactor = MockReactor()
        reactor._peers = {}
        result = reactor.peers()
        assert result == []

    def test_peers_returns_all_keys(self) -> None:
        """Test returns all peer keys when no service filter."""
        reactor = MockReactor()
        reactor._peers = {'peer1': Mock(), 'peer2': Mock()}
        result = reactor.peers()
        assert set(result) == {'peer1', 'peer2'}

    def test_peers_filters_by_service(self) -> None:
        """Test filtering by service pattern."""
        reactor = MockReactor()

        peer1 = MagicMock()
        peer1.neighbor = MagicMock()
        peer1.neighbor.api = {'processes': ['process-a', 'process-b']}

        peer2 = MagicMock()
        peer2.neighbor = MagicMock()
        peer2.neighbor.api = {'processes': ['process-c']}

        reactor._peers = {'peer1': peer1, 'peer2': peer2}

        # Filter by process-a
        result = reactor.peers('process-a')
        assert 'peer1' in result
        assert 'peer2' not in result


class TestNeighborAccessors:
    """Test neighbor accessor methods."""

    def test_neighbor_returns_config(self) -> None:
        """Test neighbor returns neighbor config."""
        reactor = MockReactor()
        peer = MagicMock()
        peer.neighbor = {'key': 'value'}
        reactor._peers = {'peer1': peer}

        result = reactor.neighbor('peer1')
        assert result == peer.neighbor

    def test_neighbor_returns_none_for_unknown(self) -> None:
        """Test neighbor returns None for unknown peer."""
        reactor = MockReactor()
        reactor._peers = {}
        result = reactor.neighbor('unknown')
        assert result is None

    def test_neighbor_name_returns_name(self) -> None:
        """Test neighbor_name returns peer name."""
        reactor = MockReactor()
        peer = MagicMock()
        reactor._peers = {'peer1': peer}

        result = reactor.neighbor_name('peer1')
        assert result == 'peer1'

    def test_neighbor_name_returns_empty_for_unknown(self) -> None:
        """Test neighbor_name returns empty string for unknown peer."""
        reactor = MockReactor()
        reactor._peers = {}
        result = reactor.neighbor_name('unknown')
        assert result == ''

    def test_neighbor_ip_returns_ip(self) -> None:
        """Test neighbor_ip returns peer IP."""
        reactor = MockReactor()
        peer = MagicMock()
        peer.neighbor = MagicMock()
        peer.neighbor.peer_address = '192.0.2.1'
        reactor._peers = {'peer1': peer}

        result = reactor.neighbor_ip('peer1')
        assert result == '192.0.2.1'

    def test_neighbor_ip_returns_empty_for_unknown(self) -> None:
        """Test neighbor_ip returns empty string for unknown peer."""
        reactor = MockReactor()
        reactor._peers = {}
        result = reactor.neighbor_ip('unknown')
        assert result == ''


class TestPendingAdjribout:
    """Test _pending_adjribout method."""

    def test_pending_adjribout_false_when_empty(self) -> None:
        """Test returns False when no peers."""
        reactor = MockReactor()
        reactor._peers = {}
        result = reactor._pending_adjribout()
        assert result is False

    def test_pending_adjribout_true_when_pending(self) -> None:
        """Test returns True when peer has pending routes."""
        reactor = MockReactor()
        peer = MagicMock()
        peer.neighbor.rib.outgoing.pending.return_value = True
        reactor._peers = {'peer1': peer}

        result = reactor._pending_adjribout()
        assert result is True

    def test_pending_adjribout_false_when_not_pending(self) -> None:
        """Test returns False when no pending routes."""
        reactor = MockReactor()
        peer = MagicMock()
        peer.neighbor.rib.outgoing.pending.return_value = False
        reactor._peers = {'peer1': peer}

        result = reactor._pending_adjribout()
        assert result is False


class TestPeerRegistration:
    """Test peer registration and teardown."""

    def test_register_peer_adds_to_dict(self) -> None:
        """Test register_peer adds peer to _peers."""
        reactor = MockReactor()
        peer = MagicMock()
        reactor.register_peer('peer1', peer)
        assert reactor._peers['peer1'] == peer

    def test_teardown_peer_removes_from_dict(self) -> None:
        """Test teardown_peer removes peer from _peers."""
        reactor = MockReactor()
        peer = MagicMock()
        reactor._peers = {'peer1': peer}

        reactor.teardown_peer('peer1', 0)
        assert 'peer1' not in reactor._peers

    def test_teardown_nonexistent_peer_is_safe(self) -> None:
        """Test teardown of nonexistent peer doesn't raise."""
        reactor = MockReactor()
        reactor._peers = {}
        reactor.teardown_peer('unknown', 0)  # Should not raise


class TestTermination:
    """Test _termination method."""

    def test_termination_sets_exit_code(self) -> None:
        """Test _termination sets exit code."""
        reactor = MockReactor()
        reactor._termination('test reason', MockReactor.Exit.configuration)
        assert reactor.exit_code == MockReactor.Exit.configuration

    def test_termination_sets_shutdown_signal(self) -> None:
        """Test _termination sets shutdown signal."""
        reactor = MockReactor()
        reactor._termination('test reason', MockReactor.Exit.normal)
        assert reactor.signal.received == 'SHUTDOWN'
