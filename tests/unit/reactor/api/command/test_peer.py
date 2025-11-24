"""Unit tests for peer management API commands (create/delete)."""

from __future__ import annotations

import pytest

from exabgp.protocol.ip import IP
from exabgp.protocol.family import AFI, SAFI
from exabgp.bgp.message.open.routerid import RouterID
from exabgp.reactor.api.command.peer import (
    _parse_ip,
    _parse_asn,
    _parse_families,
    _parse_neighbor_params,
    _build_neighbor,
)


class TestParseIP:
    """Test IP address parsing."""

    def test_valid_ipv4(self):
        ip = _parse_ip('192.168.1.1')
        assert str(ip) == '192.168.1.1'
        assert ip.afi == AFI.ipv4

    def test_valid_ipv6(self):
        ip = _parse_ip('2001:db8::1')
        assert ip.afi == AFI.ipv6

    def test_invalid_ip(self):
        with pytest.raises(ValueError, match='invalid IP address'):
            _parse_ip('not-an-ip')

    def test_empty_ip(self):
        with pytest.raises(ValueError, match='invalid IP address'):
            _parse_ip('')


class TestParseASN:
    """Test ASN parsing."""

    def test_valid_asn_16bit(self):
        assert _parse_asn('65000') == 65000

    def test_valid_asn_32bit(self):
        assert _parse_asn('4200000000') == 4200000000

    def test_asn_zero(self):
        assert _parse_asn('0') == 0

    def test_asn_max(self):
        assert _parse_asn('4294967295') == 4294967295

    def test_negative_asn(self):
        with pytest.raises(ValueError, match='ASN out of range'):
            _parse_asn('-1')

    def test_asn_too_large(self):
        with pytest.raises(ValueError, match='ASN out of range'):
            _parse_asn('4294967296')

    def test_non_numeric_asn(self):
        with pytest.raises(ValueError, match='invalid ASN'):
            _parse_asn('not-a-number')


class TestParseFamilies:
    """Test family-allowed parsing."""

    def test_single_family(self):
        families = _parse_families('ipv4-unicast')
        assert len(families) == 1
        assert families[0] == (AFI.ipv4, SAFI.unicast)

    def test_multiple_families(self):
        families = _parse_families('ipv4-unicast/ipv6-unicast')
        assert len(families) == 2
        assert (AFI.ipv4, SAFI.unicast) in families
        assert (AFI.ipv6, SAFI.unicast) in families

    def test_in_open(self):
        families = _parse_families('in-open')
        assert families == []

    def test_invalid_format(self):
        with pytest.raises(ValueError, match='invalid family format'):
            _parse_families('ipv4')


class TestParseNeighborParams:
    """Test neighbor parameter parsing from command line."""

    def test_minimal_params(self):
        line = 'neighbor 127.0.0.1 local-ip 127.0.0.1 local-as 65000 peer-as 65001 router-id 1.2.3.4 create'
        params, api_processes = _parse_neighbor_params(line)

        assert str(params['peer-address']) == '127.0.0.1'
        assert str(params['local-address']) == '127.0.0.1'
        assert params['local-as'] == 65000
        assert params['peer-as'] == 65001
        assert str(params['router-id']) == '1.2.3.4'
        assert 'families' not in params
        assert api_processes is None

    def test_all_params(self):
        line = 'neighbor 10.0.0.2 local-ip 10.0.0.1 local-as 65000 peer-as 65001 router-id 1.2.3.4 family-allowed ipv4-unicast/ipv6-unicast create'
        params, api_processes = _parse_neighbor_params(line)

        assert str(params['peer-address']) == '10.0.0.2'
        assert str(params['local-address']) == '10.0.0.1'
        assert params['local-as'] == 65000
        assert params['peer-as'] == 65001
        assert str(params['router-id']) == '1.2.3.4'
        assert len(params['families']) == 2
        assert api_processes is None

    def test_with_single_api_process(self):
        line = 'neighbor 127.0.0.1 local-ip 127.0.0.1 local-as 65000 peer-as 65001 router-id 1.2.3.4 create api peer-lifecycle'
        params, api_processes = _parse_neighbor_params(line)

        assert str(params['peer-address']) == '127.0.0.1'
        assert api_processes == ['peer-lifecycle']

    def test_with_multiple_api_processes(self):
        line = 'neighbor 127.0.0.1 local-ip 127.0.0.1 local-as 65000 peer-as 65001 router-id 1.2.3.4 create api proc1 api proc2 api proc3'
        params, api_processes = _parse_neighbor_params(line)

        assert str(params['peer-address']) == '127.0.0.1'
        assert api_processes == ['proc1', 'proc2', 'proc3']

    def test_ipv6_neighbor(self):
        line = 'neighbor 2001:db8::2 local-ip 2001:db8::1 local-as 65000 peer-as 65001 router-id 1.2.3.4 create'
        params, api_processes = _parse_neighbor_params(line)

        assert params['peer-address'].afi == AFI.ipv6

    def test_wrong_command(self):
        line = 'neighbor 127.0.0.1 local-as 65000 delete'
        with pytest.raises(ValueError, match='expected "create" command'):
            _parse_neighbor_params(line)

    def test_no_neighbor(self):
        line = 'create'
        with pytest.raises(ValueError, match='no neighbor selector'):
            _parse_neighbor_params(line)


class TestBuildNeighbor:
    """Test Neighbor object construction from parameters."""

    def test_minimal_neighbor(self):
        params = {
            'peer-address': IP.create('127.0.0.1'),
            'local-address': IP.create('127.0.0.1'),
            'local-as': 65000,
            'peer-as': 65001,
            'router-id': RouterID.create('1.2.3.4'),
        }

        neighbor = _build_neighbor(params)

        assert str(neighbor['peer-address']) == '127.0.0.1'
        assert str(neighbor['local-address']) == '127.0.0.1'
        assert neighbor['local-as'] == 65000
        assert neighbor['peer-as'] == 65001
        assert str(neighbor['router-id']) == '1.2.3.4'
        assert len(neighbor.families()) == 1  # Default IPv4 unicast
        assert (AFI.ipv4, SAFI.unicast) in neighbor.families()

    def test_neighbor_with_different_local_address(self):
        params = {
            'peer-address': IP.create('10.0.0.2'),
            'local-address': IP.create('10.0.0.1'),
            'local-as': 65000,
            'peer-as': 65001,
            'router-id': RouterID.create('1.2.3.4'),
        }

        neighbor = _build_neighbor(params)

        assert str(neighbor['local-address']) == '10.0.0.1'

    def test_neighbor_with_api_processes(self):
        params = {
            'peer-address': IP.create('127.0.0.1'),
            'local-address': IP.create('127.0.0.1'),
            'local-as': 65000,
            'peer-as': 65001,
            'router-id': RouterID.create('1.2.3.4'),
        }

        neighbor = _build_neighbor(params, api_processes=['proc1', 'proc2'])

        assert neighbor.api['processes'] == ['proc1', 'proc2']

    def test_neighbor_without_api_processes(self):
        params = {
            'peer-address': IP.create('127.0.0.1'),
            'local-address': IP.create('127.0.0.1'),
            'local-as': 65000,
            'peer-as': 65001,
            'router-id': RouterID.create('1.2.3.4'),
        }

        neighbor = _build_neighbor(params)

        # Should use default (empty processes list)
        assert neighbor.api['processes'] == []

    def test_neighbor_with_families(self):
        params = {
            'peer-address': IP.create('127.0.0.1'),
            'local-address': IP.create('127.0.0.1'),
            'local-as': 65000,
            'peer-as': 65001,
            'router-id': RouterID.create('1.2.3.4'),
            'families': [(AFI.ipv4, SAFI.unicast), (AFI.ipv6, SAFI.unicast)],
        }

        neighbor = _build_neighbor(params)

        assert len(neighbor.families()) == 2
        assert (AFI.ipv4, SAFI.unicast) in neighbor.families()
        assert (AFI.ipv6, SAFI.unicast) in neighbor.families()

    def test_missing_peer_address(self):
        params = {
            'local-address': IP.create('127.0.0.1'),
            'local-as': 65000,
            'peer-as': 65001,
            'router-id': RouterID.create('1.2.3.4'),
        }

        with pytest.raises(ValueError, match='missing required parameter: peer-address'):
            _build_neighbor(params)

    def test_missing_local_ip(self):
        params = {
            'peer-address': IP.create('127.0.0.1'),
            'local-as': 65000,
            'peer-as': 65001,
            'router-id': RouterID.create('1.2.3.4'),
        }

        with pytest.raises(ValueError, match='missing required parameter: local-ip'):
            _build_neighbor(params)

    def test_missing_local_as(self):
        params = {
            'peer-address': IP.create('127.0.0.1'),
            'local-address': IP.create('127.0.0.1'),
            'peer-as': 65001,
            'router-id': RouterID.create('1.2.3.4'),
        }

        with pytest.raises(ValueError, match='missing required parameter: local-as'):
            _build_neighbor(params)

    def test_missing_peer_as(self):
        params = {
            'peer-address': IP.create('127.0.0.1'),
            'local-address': IP.create('127.0.0.1'),
            'local-as': 65000,
            'router-id': RouterID.create('1.2.3.4'),
        }

        with pytest.raises(ValueError, match='missing required parameter: peer-as'):
            _build_neighbor(params)

    def test_missing_router_id(self):
        params = {
            'peer-address': IP.create('127.0.0.1'),
            'local-address': IP.create('127.0.0.1'),
            'local-as': 65000,
            'peer-as': 65001,
        }

        with pytest.raises(ValueError, match='missing required parameter: router-id'):
            _build_neighbor(params)


class TestEndToEnd:
    """End-to-end integration tests for parameter parsing and neighbor building."""

    def test_complete_flow(self):
        """Test parsing command line and building neighbor."""
        line = 'neighbor 10.0.0.2 local-ip 10.0.0.1 local-as 65000 peer-as 65001 router-id 1.2.3.4 family-allowed ipv4-unicast create'

        params, api_processes = _parse_neighbor_params(line)
        neighbor = _build_neighbor(params, api_processes)

        # Verify neighbor is properly configured
        assert str(neighbor['peer-address']) == '10.0.0.2'
        assert str(neighbor['local-address']) == '10.0.0.1'
        assert neighbor['local-as'] == 65000
        assert neighbor['peer-as'] == 65001
        assert str(neighbor['router-id']) == '1.2.3.4'
        assert len(neighbor.families()) == 1
        assert neighbor.rib is not None  # RIB created

    def test_ipv6_flow(self):
        """Test IPv6 neighbor creation."""
        line = 'neighbor 2001:db8::2 local-ip 2001:db8::1 local-as 65000 peer-as 65001 router-id 1.2.3.4 family-allowed ipv6-unicast create'

        params, api_processes = _parse_neighbor_params(line)
        neighbor = _build_neighbor(params, api_processes)

        assert neighbor['peer-address'].afi == AFI.ipv6
        assert neighbor['local-address'].afi == AFI.ipv6
        assert (AFI.ipv6, SAFI.unicast) in neighbor.families()


class TestNeighborCreateCommand:
    """Test neighbor_create API command handler."""

    @pytest.fixture
    def mock_reactor(self):
        """Create mock reactor for testing."""
        from unittest.mock import Mock
        from exabgp.configuration.configuration import Configuration

        reactor = Mock()
        reactor._peers = {}
        reactor._dynamic_peers = set()
        reactor.configuration = Configuration([])
        reactor.configuration.neighbors = {}

        # Mock processes
        reactor.processes = Mock()
        reactor.processes._answer = Mock()
        reactor.processes.answer_error = Mock()

        return reactor

    def test_create_new_peer_success(self, mock_reactor):
        """Test creating a new peer successfully."""
        from exabgp.reactor.api.command.peer import neighbor_create

        command = 'create neighbor 127.0.0.1 local-address 127.0.0.1 local-as 65000 peer-as 65001 router-id 1.2.3.4'
        result = neighbor_create(None, mock_reactor, 'test-service', command, False)

        assert result is True
        mock_reactor.processes._answer.assert_called_once_with('test-service', 'done')
        assert len(mock_reactor._peers) == 1
        assert len(mock_reactor._dynamic_peers) == 1

    def test_create_duplicate_peer(self, mock_reactor):
        """Test creating a peer that already exists."""
        from exabgp.reactor.api.command.peer import neighbor_create

        command = 'create neighbor 127.0.0.1 local-address 127.0.0.1 local-as 65000 peer-as 65001 router-id 1.2.3.4'

        # Create first peer
        result1 = neighbor_create(None, mock_reactor, 'test-service', command, False)
        assert result1 is True

        # Try to create duplicate
        result2 = neighbor_create(None, mock_reactor, 'test-service', command, False)
        assert result2 is False
        mock_reactor.processes.answer_error.assert_called()
        error_msg = mock_reactor.processes.answer_error.call_args[0][1]
        assert 'peer already exists' in error_msg

    def test_create_with_invalid_ip(self, mock_reactor):
        """Test creating peer with invalid IP address."""
        from exabgp.reactor.api.command.peer import neighbor_create

        command = 'create neighbor 999.999.999.999 local-address 127.0.0.1 local-as 65000 peer-as 65001'
        result = neighbor_create(None, mock_reactor, 'test-service', command, False)

        assert result is False
        mock_reactor.processes.answer_error.assert_called()

    def test_create_with_missing_params(self, mock_reactor):
        """Test creating peer with missing required parameters."""
        from exabgp.reactor.api.command.peer import neighbor_create

        command = 'create neighbor 127.0.0.1 local-as 65000'
        result = neighbor_create(None, mock_reactor, 'test-service', command, False)

        assert result is False
        mock_reactor.processes.answer_error.assert_called()

    def test_create_multiple_peers(self, mock_reactor):
        """Test creating multiple different peers."""
        from exabgp.reactor.api.command.peer import neighbor_create

        commands = [
            'create neighbor 127.0.0.1 local-address 127.0.0.1 local-as 65000 peer-as 65001 router-id 1.2.3.4',
            'create neighbor 127.0.0.2 local-address 127.0.0.1 local-as 65000 peer-as 65002 router-id 1.2.3.5',
            'create neighbor 10.0.0.1 local-address 10.0.0.2 local-as 65003 peer-as 65004 router-id 1.2.3.6',
        ]

        for cmd in commands:
            result = neighbor_create(None, mock_reactor, 'test-service', cmd, False)
            assert result is True

        assert len(mock_reactor._peers) == 3
        assert len(mock_reactor._dynamic_peers) == 3

    def test_create_peer_validates_configuration(self, mock_reactor):
        """Test that created peer has correct configuration."""
        from exabgp.reactor.api.command.peer import neighbor_create
        from exabgp.protocol.family import AFI, SAFI

        command = 'create neighbor 10.0.0.2 local-address 10.0.0.1 local-as 65000 peer-as 65001 router-id 2.3.4.5 family-allowed ipv4-unicast/ipv6-unicast'
        result = neighbor_create(None, mock_reactor, 'test-service', command, False)

        assert result is True
        assert len(mock_reactor._peers) == 1

        # Get the created peer
        peer_key = list(mock_reactor._peers.keys())[0]
        peer = mock_reactor._peers[peer_key]

        # Verify peer neighbor configuration
        neighbor = peer.neighbor
        assert str(neighbor['peer-address']) == '10.0.0.2'
        assert str(neighbor['local-address']) == '10.0.0.1'
        assert neighbor['local-as'] == 65000
        assert neighbor['peer-as'] == 65001
        assert str(neighbor['router-id']) == '2.3.4.5'

        # Verify families
        families = neighbor.families()
        assert len(families) == 2
        assert (AFI.ipv4, SAFI.unicast) in families
        assert (AFI.ipv6, SAFI.unicast) in families

        # Verify RIB created
        assert neighbor.rib is not None

    def test_create_with_api_processes_stored(self, mock_reactor):
        """Test that API processes are correctly stored in peer configuration."""
        from exabgp.reactor.api.command.peer import neighbor_create

        command = 'create neighbor 127.0.0.1 local-address 127.0.0.1 local-as 65000 peer-as 65001 router-id 1.2.3.4 api proc1 api proc2'
        result = neighbor_create(None, mock_reactor, 'test-service', command, False)

        assert result is True

        # Get the created peer
        peer = list(mock_reactor._peers.values())[0]
        neighbor = peer.neighbor

        # Verify API processes
        assert neighbor.api['processes'] == ['proc1', 'proc2']

    def test_create_peer_key_uniqueness(self, mock_reactor):
        """Test that peer key correctly distinguishes different neighbors."""
        from exabgp.reactor.api.command.peer import neighbor_create

        # Create two peers with same peer-address but different local-address
        commands = [
            'create neighbor 127.0.0.1 local-address 10.0.0.1 local-as 65000 peer-as 65001 router-id 1.2.3.4',
            'create neighbor 127.0.0.1 local-address 10.0.0.2 local-as 65000 peer-as 65001 router-id 1.2.3.4',
        ]

        for cmd in commands:
            result = neighbor_create(None, mock_reactor, 'test-service', cmd, False)
            assert result is True

        # Should have 2 distinct peers (different local-address = different keys)
        assert len(mock_reactor._peers) == 2

        # Verify they have different local addresses
        peers = list(mock_reactor._peers.values())
        local_addrs = {str(p.neighbor['local-address']) for p in peers}
        assert local_addrs == {'10.0.0.1', '10.0.0.2'}


class TestNeighborDeleteCommand:
    """Test neighbor_delete API command handler."""

    @pytest.fixture
    def mock_reactor_with_peers(self):
        """Create mock reactor with pre-existing peers."""
        from unittest.mock import Mock, patch
        from exabgp.configuration.configuration import Configuration
        from exabgp.reactor.api.command.peer import neighbor_create

        reactor = Mock()
        reactor._peers = {}
        reactor._dynamic_peers = set()
        reactor.configuration = Configuration([])
        reactor.configuration.neighbors = {}
        reactor.processes = Mock()
        reactor.processes._answer = Mock()
        reactor.processes.answer_error = Mock()
        reactor.processes.answer_done = Mock()

        # Create test peers
        commands = [
            'create neighbor 127.0.0.1 local-address 127.0.0.1 local-as 65000 peer-as 65001 router-id 1.2.3.4',
            'create neighbor 127.0.0.2 local-address 127.0.0.1 local-as 65000 peer-as 65002 router-id 1.2.3.5',
        ]

        for cmd in commands:
            neighbor_create(None, reactor, 'test-service', cmd, False)

        # Add remove() method to all created peers
        for key, peer in list(reactor._peers.items()):
            peer.remove = Mock()

        # Mock peers() method for selector matching - returns all peer keys
        def peers_func(service):
            return list(reactor._peers.keys())

        reactor.peers = peers_func

        return reactor

    def test_delete_existing_peer(self, mock_reactor_with_peers):
        """Test deleting an existing peer."""
        from unittest.mock import patch
        from exabgp.reactor.api.command.peer import neighbor_delete

        initial_count = len(mock_reactor_with_peers._peers)
        all_peers = list(mock_reactor_with_peers._peers.keys())
        target_peer = [key for key in all_peers if '127.0.0.1' in key][0]

        command = 'neighbor 127.0.0.1'

        # Mock match_neighbors to return only the matching peer
        with patch('exabgp.reactor.api.command.peer.match_neighbors', return_value=[target_peer]):
            result = neighbor_delete(None, mock_reactor_with_peers, 'test-service', command, False)

        assert result is True
        mock_reactor_with_peers.processes.answer_done.assert_called_once()
        assert len(mock_reactor_with_peers._peers) == initial_count - 1

    def test_delete_nonexistent_peer(self, mock_reactor_with_peers):
        """Test deleting a peer that doesn't exist."""
        from unittest.mock import patch
        from exabgp.reactor.api.command.peer import neighbor_delete

        command = 'neighbor 192.168.1.1'

        # Mock match_neighbors to return empty list (no matches)
        with patch('exabgp.reactor.api.command.peer.match_neighbors', return_value=[]):
            result = neighbor_delete(None, mock_reactor_with_peers, 'test-service', command, False)

        assert result is False
        mock_reactor_with_peers.processes.answer_error.assert_called()
        error_msg = mock_reactor_with_peers.processes.answer_error.call_args[0][1]
        assert 'no neighbors match' in error_msg

    def test_delete_all_peers(self, mock_reactor_with_peers):
        """Test deleting all peers with wildcard selector."""
        from exabgp.reactor.api.command.peer import neighbor_delete

        initial_count = len(mock_reactor_with_peers._peers)
        command = 'neighbor *'
        result = neighbor_delete(None, mock_reactor_with_peers, 'test-service', command, False)

        assert result is True
        assert len(mock_reactor_with_peers._peers) < initial_count

    def test_delete_with_missing_selector(self, mock_reactor_with_peers):
        """Test delete command with missing neighbor selector."""
        from exabgp.reactor.api.command.peer import neighbor_delete

        command = 'delete'
        result = neighbor_delete(None, mock_reactor_with_peers, 'test-service', command, False)

        assert result is False
        mock_reactor_with_peers.processes.answer_error.assert_called()
        error_msg = mock_reactor_with_peers.processes.answer_error.call_args[0][1]
        assert 'missing neighbor selector' in error_msg

    def test_delete_verifies_peer_removed(self, mock_reactor_with_peers):
        """Test that delete properly removes peer from all data structures."""
        from unittest.mock import patch
        from exabgp.reactor.api.command.peer import neighbor_delete

        # Get initial state
        all_peers = list(mock_reactor_with_peers._peers.keys())
        target_peer = [key for key in all_peers if '127.0.0.1' in key][0]
        initial_peers = len(mock_reactor_with_peers._peers)
        initial_config = len(mock_reactor_with_peers.configuration.neighbors)
        initial_dynamic = len(mock_reactor_with_peers._dynamic_peers)

        command = 'neighbor 127.0.0.1'

        # Mock match_neighbors to return the target peer
        with patch('exabgp.reactor.api.command.peer.match_neighbors', return_value=[target_peer]):
            result = neighbor_delete(None, mock_reactor_with_peers, 'test-service', command, False)

        assert result is True

        # Verify peer removed from all structures
        assert len(mock_reactor_with_peers._peers) == initial_peers - 1
        assert len(mock_reactor_with_peers.configuration.neighbors) == initial_config - 1
        assert len(mock_reactor_with_peers._dynamic_peers) == initial_dynamic - 1

        # Verify specific peer is gone
        assert target_peer not in mock_reactor_with_peers._peers
        assert target_peer not in mock_reactor_with_peers.configuration.neighbors
        assert target_peer not in mock_reactor_with_peers._dynamic_peers

        # Verify peer.remove() was called
        # (Peer object was already deleted, but we mocked remove() earlier)

    def test_delete_keeps_other_peers_intact(self, mock_reactor_with_peers):
        """Test that deleting one peer doesn't affect others."""
        from unittest.mock import patch
        from exabgp.reactor.api.command.peer import neighbor_delete

        # Get all peer keys and configurations before delete
        all_peers = list(mock_reactor_with_peers._peers.keys())
        target_peer = [key for key in all_peers if '127.0.0.1' in key][0]
        other_peers = [key for key in all_peers if key != target_peer]

        # Store other peer data before deletion
        other_peer_data = {}
        for key in other_peers:
            peer = mock_reactor_with_peers._peers[key]
            other_peer_data[key] = {
                'peer-address': str(peer.neighbor['peer-address']),
                'local-as': peer.neighbor['local-as'],
            }

        command = 'neighbor 127.0.0.1'

        # Delete the target peer
        with patch('exabgp.reactor.api.command.peer.match_neighbors', return_value=[target_peer]):
            result = neighbor_delete(None, mock_reactor_with_peers, 'test-service', command, False)

        assert result is True

        # Verify other peers still exist
        for key in other_peers:
            assert key in mock_reactor_with_peers._peers
            peer = mock_reactor_with_peers._peers[key]

            # Verify configuration unchanged
            assert str(peer.neighbor['peer-address']) == other_peer_data[key]['peer-address']
            assert peer.neighbor['local-as'] == other_peer_data[key]['local-as']

    def test_delete_calls_peer_remove(self, mock_reactor_with_peers):
        """Test that delete calls peer.remove() for graceful TCP teardown."""
        from unittest.mock import patch
        from exabgp.reactor.api.command.peer import neighbor_delete

        # Get target peer
        all_peers = list(mock_reactor_with_peers._peers.keys())
        target_peer = [key for key in all_peers if '127.0.0.1' in key][0]
        peer_obj = mock_reactor_with_peers._peers[target_peer]

        command = 'neighbor 127.0.0.1'

        # Delete the peer
        with patch('exabgp.reactor.api.command.peer.match_neighbors', return_value=[target_peer]):
            result = neighbor_delete(None, mock_reactor_with_peers, 'test-service', command, False)

        assert result is True

        # Verify peer.remove() was called (TCP teardown)
        peer_obj.remove.assert_called_once()

    def test_delete_removes_key_from_all_structures(self, mock_reactor_with_peers):
        """Test that delete removes peer key from reactor, config, and dynamic tracking."""
        from unittest.mock import patch
        from exabgp.reactor.api.command.peer import neighbor_delete

        # Get target peer key
        all_peers = list(mock_reactor_with_peers._peers.keys())
        target_peer = [key for key in all_peers if '127.0.0.2' in key][0]

        # Verify key exists before deletion
        assert target_peer in mock_reactor_with_peers._peers
        assert target_peer in mock_reactor_with_peers.configuration.neighbors
        assert target_peer in mock_reactor_with_peers._dynamic_peers

        command = 'neighbor 127.0.0.2'

        # Delete the peer
        with patch('exabgp.reactor.api.command.peer.match_neighbors', return_value=[target_peer]):
            result = neighbor_delete(None, mock_reactor_with_peers, 'test-service', command, False)

        assert result is True

        # Verify key removed from ALL structures
        assert target_peer not in mock_reactor_with_peers._peers
        assert target_peer not in mock_reactor_with_peers.configuration.neighbors
        assert target_peer not in mock_reactor_with_peers._dynamic_peers

    def test_delete_graceful_shutdown_order(self, mock_reactor_with_peers):
        """Test that delete follows correct order: remove() BEFORE deleting from structures."""
        from unittest.mock import patch, Mock, call
        from exabgp.reactor.api.command.peer import neighbor_delete

        # Track operation order
        operations = []

        # Get target peer
        all_peers = list(mock_reactor_with_peers._peers.keys())
        target_peer = [key for key in all_peers if '127.0.0.1' in key][0]
        peer_obj = mock_reactor_with_peers._peers[target_peer]

        # Mock remove to record when it's called
        def mock_remove():
            operations.append('remove')
            # Check peer still in structures when remove() called
            assert target_peer in mock_reactor_with_peers._peers
            assert target_peer in mock_reactor_with_peers.configuration.neighbors

        peer_obj.remove = Mock(side_effect=mock_remove)

        command = 'neighbor 127.0.0.1'

        # Delete the peer
        with patch('exabgp.reactor.api.command.peer.match_neighbors', return_value=[target_peer]):
            result = neighbor_delete(None, mock_reactor_with_peers, 'test-service', command, False)

        assert result is True

        # Verify remove() was called first (peer still existed in structures at that point)
        assert operations == ['remove']

        # Verify peer removed from structures AFTER remove() completed
        assert target_peer not in mock_reactor_with_peers._peers
