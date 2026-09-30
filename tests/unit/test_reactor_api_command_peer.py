"""Unit tests for peer management API commands (create/delete)."""

from __future__ import annotations

import os
from collections.abc import Iterator
from typing import Any
from unittest.mock import patch

import pytest

from exabgp.configuration.configuration import Configuration
from exabgp.reactor.api.processes import Processes
from exabgp.reactor.loop import Reactor

from exabgp.protocol.ip import IP
from exabgp.protocol.family import AFI, SAFI
from exabgp.bgp.message.open.asn import ASN
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
        assert api_processes == []

    def test_all_params(self):
        line = 'neighbor 10.0.0.2 local-ip 10.0.0.1 local-as 65000 peer-as 65001 router-id 1.2.3.4 family-allowed ipv4-unicast/ipv6-unicast create'
        params, api_processes = _parse_neighbor_params(line)

        assert str(params['peer-address']) == '10.0.0.2'
        assert str(params['local-address']) == '10.0.0.1'
        assert params['local-as'] == 65000
        assert params['peer-as'] == 65001
        assert str(params['router-id']) == '1.2.3.4'
        assert len(params['families']) == 2
        assert api_processes == []

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
            'peer-address': IP.from_string('127.0.0.1'),
            'local-address': IP.from_string('127.0.0.1'),
            'local-as': ASN(65000),
            'peer-as': ASN(65001),
            'router-id': RouterID('1.2.3.4'),
        }

        neighbor = _build_neighbor(params)

        assert str(neighbor.session.peer_address) == '127.0.0.1'
        assert str(neighbor.session.local_address) == '127.0.0.1'
        assert neighbor.session.local_as == 65000
        assert neighbor.session.peer_as == 65001
        assert str(neighbor.session.router_id) == '1.2.3.4'
        assert len(neighbor.families()) == 1  # Default IPv4 unicast
        assert (AFI.ipv4, SAFI.unicast) in neighbor.families()

    def test_neighbor_with_different_local_address(self):
        params = {
            'peer-address': IP.from_string('10.0.0.2'),
            'local-address': IP.from_string('10.0.0.1'),
            'local-as': ASN(65000),
            'peer-as': ASN(65001),
            'router-id': RouterID('1.2.3.4'),
        }

        neighbor = _build_neighbor(params)

        assert str(neighbor.session.local_address) == '10.0.0.1'

    def test_neighbor_with_api_processes(self):
        params = {
            'peer-address': IP.from_string('127.0.0.1'),
            'local-address': IP.from_string('127.0.0.1'),
            'local-as': ASN(65000),
            'peer-as': ASN(65001),
            'router-id': RouterID('1.2.3.4'),
        }

        neighbor = _build_neighbor(params, api_processes=['proc1', 'proc2'])

        assert neighbor.api['processes'] == ['proc1', 'proc2']

    def test_neighbor_without_api_processes(self):
        params = {
            'peer-address': IP.from_string('127.0.0.1'),
            'local-address': IP.from_string('127.0.0.1'),
            'local-as': ASN(65000),
            'peer-as': ASN(65001),
            'router-id': RouterID('1.2.3.4'),
        }

        neighbor = _build_neighbor(params)

        # Should use default (empty processes list)
        assert neighbor.api['processes'] == []

    def test_neighbor_with_families(self):
        params = {
            'peer-address': IP.from_string('127.0.0.1'),
            'local-address': IP.from_string('127.0.0.1'),
            'local-as': ASN(65000),
            'peer-as': ASN(65001),
            'router-id': RouterID('1.2.3.4'),
            'families': [(AFI.ipv4, SAFI.unicast), (AFI.ipv6, SAFI.unicast)],
        }

        neighbor = _build_neighbor(params)

        assert len(neighbor.families()) == 2
        assert (AFI.ipv4, SAFI.unicast) in neighbor.families()
        assert (AFI.ipv6, SAFI.unicast) in neighbor.families()

    def test_missing_peer_address(self):
        params = {
            'local-address': IP.from_string('127.0.0.1'),
            'local-as': ASN(65000),
            'peer-as': ASN(65001),
            'router-id': RouterID('1.2.3.4'),
        }

        with pytest.raises(ValueError, match='missing required parameter: peer-address'):
            _build_neighbor(params)

    def test_missing_local_ip(self):
        params = {
            'peer-address': IP.from_string('127.0.0.1'),
            'local-as': ASN(65000),
            'peer-as': ASN(65001),
            'router-id': RouterID('1.2.3.4'),
        }

        with pytest.raises(ValueError, match='missing required parameter: local-ip'):
            _build_neighbor(params)

    def test_missing_local_as(self):
        params = {
            'peer-address': IP.from_string('127.0.0.1'),
            'local-address': IP.from_string('127.0.0.1'),
            'peer-as': ASN(65001),
            'router-id': RouterID('1.2.3.4'),
        }

        with pytest.raises(ValueError, match='missing required parameter: local-as'):
            _build_neighbor(params)

    def test_missing_peer_as(self):
        params = {
            'peer-address': IP.from_string('127.0.0.1'),
            'local-address': IP.from_string('127.0.0.1'),
            'local-as': ASN(65000),
            'router-id': RouterID('1.2.3.4'),
        }

        with pytest.raises(ValueError, match='missing required parameter: peer-as'):
            _build_neighbor(params)

    def test_missing_router_id(self):
        params = {
            'peer-address': IP.from_string('127.0.0.1'),
            'local-address': IP.from_string('127.0.0.1'),
            'local-as': ASN(65000),
            'peer-as': ASN(65001),
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
        assert str(neighbor.session.peer_address) == '10.0.0.2'
        assert str(neighbor.session.local_address) == '10.0.0.1'
        assert neighbor.session.local_as == 65000
        assert neighbor.session.peer_as == 65001
        assert str(neighbor.session.router_id) == '1.2.3.4'
        assert len(neighbor.families()) == 1
        assert neighbor.rib.enabled  # RIB created and enabled

    def test_ipv6_flow(self):
        """Test IPv6 neighbor creation."""
        line = 'neighbor 2001:db8::2 local-ip 2001:db8::1 local-as 65000 peer-as 65001 router-id 1.2.3.4 family-allowed ipv6-unicast create'

        params, api_processes = _parse_neighbor_params(line)
        neighbor = _build_neighbor(params, api_processes)

        assert neighbor.session.peer_address.afi == AFI.ipv6
        assert neighbor.session.local_address.afi == AFI.ipv6
        assert (AFI.ipv6, SAFI.unicast) in neighbor.families()


class PipedHelper:
    """The Popen of the API client, as far as answering it goes: its stdin is a pipe."""

    def __init__(self) -> None:
        self._reader, writer = os.pipe()
        os.set_blocking(self._reader, False)
        self.stdin = os.fdopen(writer, 'wb')

    def lines(self) -> list[str]:
        """Every line written to the client since the last call."""
        try:
            return os.read(self._reader, 65536).decode('ascii').splitlines()
        except BlockingIOError:
            return []

    def close(self) -> None:
        os.close(self._reader)
        self.stdin.close()


@pytest.fixture
def client() -> Iterator[PipedHelper]:
    piped = PipedHelper()
    yield piped
    piped.close()


@pytest.fixture
def reactor(client: PipedHelper) -> Reactor:
    """A real Reactor with no neighbor, whose API client 'test-service' is `client`."""
    created = Reactor(Configuration([''], text=True))
    created.configuration.neighbors = {}
    created.processes = Processes()
    created.processes._process['test-service'] = client  # type: ignore[assignment]
    created.processes._ack['test-service'] = True
    created.processes._ackjson['test-service'] = False
    return created


class TestNeighborCreateCommand:
    """Test neighbor_create API command handler."""

    def test_create_new_peer_success(self, reactor, client):
        """Test creating a new peer successfully."""
        from exabgp.reactor.api.command.peer import neighbor_create

        # command is params after "peer create" stripped
        command = '127.0.0.1 local-address 127.0.0.1 local-as 65000 peer-as 65001 router-id 1.2.3.4'
        result = neighbor_create(reactor.api, reactor, 'test-service', [], command, False)

        assert result is True
        assert client.lines() == ['done']
        assert len(reactor._peers) == 1
        assert len(reactor._dynamic_peers) == 1

    def test_create_duplicate_peer(self, reactor, client):
        """Test creating a peer that already exists."""
        from exabgp.reactor.api.command.peer import neighbor_create

        command = '127.0.0.1 local-address 127.0.0.1 local-as 65000 peer-as 65001 router-id 1.2.3.4'

        # Create first peer
        result1 = neighbor_create(reactor.api, reactor, 'test-service', [], command, False)
        assert result1 is True

        # Try to create duplicate
        result2 = neighbor_create(reactor.api, reactor, 'test-service', [], command, False)
        assert result2 is False
        answers = client.lines()
        assert answers[-1] == 'error'
        assert any(line.startswith('error: peer already exists') for line in answers)

    def test_create_with_invalid_ip(self, reactor, client):
        """Test creating peer with invalid IP address."""
        from exabgp.reactor.api.command.peer import neighbor_create

        command = '999.999.999.999 local-address 127.0.0.1 local-as 65000 peer-as 65001'
        result = neighbor_create(reactor.api, reactor, 'test-service', [], command, False)

        assert result is False
        assert client.lines()[-1] == 'error'

    def test_create_with_missing_params(self, reactor, client):
        """Test creating peer with missing required parameters."""
        from exabgp.reactor.api.command.peer import neighbor_create

        command = '127.0.0.1 local-as 65000'
        result = neighbor_create(reactor.api, reactor, 'test-service', [], command, False)

        assert result is False
        assert client.lines()[-1] == 'error'

    def test_create_multiple_peers(self, reactor, client):
        """Test creating multiple different peers."""
        from exabgp.reactor.api.command.peer import neighbor_create

        commands = [
            '127.0.0.1 local-address 127.0.0.1 local-as 65000 peer-as 65001 router-id 1.2.3.4',
            '127.0.0.2 local-address 127.0.0.1 local-as 65000 peer-as 65002 router-id 1.2.3.5',
            '10.0.0.1 local-address 10.0.0.2 local-as 65003 peer-as 65004 router-id 1.2.3.6',
        ]

        for cmd in commands:
            result = neighbor_create(reactor.api, reactor, 'test-service', [], cmd, False)
            assert result is True

        assert len(reactor._peers) == 3
        assert len(reactor._dynamic_peers) == 3

    def test_create_peer_validates_configuration(self, reactor, client):
        """Test that created peer has correct configuration."""
        from exabgp.reactor.api.command.peer import neighbor_create
        from exabgp.protocol.family import AFI, SAFI

        command = '10.0.0.2 local-address 10.0.0.1 local-as 65000 peer-as 65001 router-id 2.3.4.5 family-allowed ipv4-unicast/ipv6-unicast'
        result = neighbor_create(reactor.api, reactor, 'test-service', [], command, False)

        assert result is True
        assert len(reactor._peers) == 1

        # Get the created peer
        peer_key = list(reactor._peers.keys())[0]
        peer = reactor._peers[peer_key]

        # Verify peer neighbor configuration
        neighbor = peer.neighbor
        assert str(neighbor.session.peer_address) == '10.0.0.2'
        assert str(neighbor.session.local_address) == '10.0.0.1'
        assert neighbor.session.local_as == 65000
        assert neighbor.session.peer_as == 65001
        assert str(neighbor.session.router_id) == '2.3.4.5'

        # Verify families
        families = neighbor.families()
        assert len(families) == 2
        assert (AFI.ipv4, SAFI.unicast) in families
        assert (AFI.ipv6, SAFI.unicast) in families

        # Verify RIB created and enabled
        assert neighbor.rib.enabled

    def test_create_with_api_processes_stored(self, reactor, client):
        """Test that API processes are correctly stored in peer configuration."""
        from exabgp.reactor.api.command.peer import neighbor_create

        command = '127.0.0.1 local-address 127.0.0.1 local-as 65000 peer-as 65001 router-id 1.2.3.4 api proc1 api proc2'
        result = neighbor_create(reactor.api, reactor, 'test-service', [], command, False)

        assert result is True

        # Get the created peer
        peer = list(reactor._peers.values())[0]
        neighbor = peer.neighbor

        # Verify API processes
        assert neighbor.api['processes'] == ['proc1', 'proc2']

    def test_create_peer_key_uniqueness(self, reactor, client):
        """Test that peer key correctly distinguishes different neighbors."""
        from exabgp.reactor.api.command.peer import neighbor_create

        # Create two peers with same peer-address but different local-address
        commands = [
            '127.0.0.1 local-address 10.0.0.1 local-as 65000 peer-as 65001 router-id 1.2.3.4',
            '127.0.0.1 local-address 10.0.0.2 local-as 65000 peer-as 65001 router-id 1.2.3.4',
        ]

        for cmd in commands:
            result = neighbor_create(reactor.api, reactor, 'test-service', [], cmd, False)
            assert result is True

        # Should have 2 distinct peers (different local-address = different keys)
        assert len(reactor._peers) == 2

        # Verify they have different local addresses
        peers = list(reactor._peers.values())
        local_addrs = {str(p.neighbor.session.local_address) for p in peers}
        assert local_addrs == {'10.0.0.1', '10.0.0.2'}


class TestPeerDeleteCommand:
    """Test peer_delete API command handler (v6 only)."""

    @pytest.fixture
    def reactor(self, reactor: Reactor, client: PipedHelper) -> Reactor:
        """The reactor, with two peers created through the API, and their answers read."""
        from exabgp.reactor.api.command.peer import neighbor_create

        # Create test peers (command is params after "peer create" stripped)
        commands = [
            '127.0.0.1 local-address 127.0.0.1 local-as 65000 peer-as 65001 router-id 1.2.3.4',
            '127.0.0.2 local-address 127.0.0.1 local-as 65000 peer-as 65002 router-id 1.2.3.5',
        ]

        for cmd in commands:
            assert neighbor_create(reactor.api, reactor, 'test-service', [], cmd, False)
        assert client.lines() == ['done', 'done']

        return reactor

    def test_delete_existing_peer(self, reactor, client):
        """Test deleting an existing peer."""
        from exabgp.reactor.api.command.peer import peer_delete

        initial_count = len(reactor._peers)
        all_peers = list(reactor._peers.keys())
        target_peer = [key for key in all_peers if '127.0.0.1' in key][0]

        # peers list is now passed directly (already matched by dispatcher)
        result = peer_delete(reactor.api, reactor, 'test-service', [target_peer], '', False)

        assert result is True
        assert client.lines() == ['done']
        assert len(reactor._peers) == initial_count - 1

    def test_delete_nonexistent_peer(self, reactor, client):
        """Test deleting a peer that doesn't exist."""
        from exabgp.reactor.api.command.peer import peer_delete

        # Empty peers list means no matches
        result = peer_delete(reactor.api, reactor, 'test-service', [], '', False)

        assert result is False
        assert client.lines() == ['error: no neighbors match the selector', 'error']

    def test_delete_all_peers(self, reactor, client):
        """Test deleting all peers with wildcard selector."""
        from exabgp.reactor.api.command.peer import peer_delete

        # All peers passed in the list
        all_peers = list(reactor._peers.keys())
        assert len(all_peers) > 0  # Verify we have peers to delete
        result = peer_delete(reactor.api, reactor, 'test-service', all_peers, '', False)

        assert result is True
        assert len(reactor._peers) == 0

    def test_delete_with_missing_selector(self, reactor, client):
        """Test delete command with missing peer selector."""
        from exabgp.reactor.api.command.peer import peer_delete

        # Empty peers list simulates no selector match
        result = peer_delete(reactor.api, reactor, 'test-service', [], '', False)

        assert result is False
        assert client.lines()[-1] == 'error'

    def test_delete_verifies_peer_removed(self, reactor, client):
        """Test that delete properly removes peer from all data structures."""
        from exabgp.reactor.api.command.peer import peer_delete

        # Get initial state
        all_peers = list(reactor._peers.keys())
        target_peer = [key for key in all_peers if '127.0.0.1' in key][0]
        initial_peers = len(reactor._peers)
        initial_config = len(reactor.configuration.neighbors)
        initial_dynamic = len(reactor._dynamic_peers)

        # Pass the matched peer directly
        result = peer_delete(reactor.api, reactor, 'test-service', [target_peer], '', False)

        assert result is True

        # Verify peer removed from all structures
        assert len(reactor._peers) == initial_peers - 1
        assert len(reactor.configuration.neighbors) == initial_config - 1
        assert len(reactor._dynamic_peers) == initial_dynamic - 1

        # Verify specific peer is gone
        assert target_peer not in reactor._peers
        assert target_peer not in reactor.configuration.neighbors
        assert target_peer not in reactor._dynamic_peers

    def test_delete_keeps_other_peers_intact(self, reactor, client):
        """Test that deleting one peer doesn't affect others."""
        from exabgp.reactor.api.command.peer import peer_delete

        # Get all peer keys and configurations before delete
        all_peers = list(reactor._peers.keys())
        target_peer = [key for key in all_peers if '127.0.0.1' in key][0]
        other_peers = [key for key in all_peers if key != target_peer]

        # Store other peer data before deletion
        other_peer_data = {}
        for key in other_peers:
            peer = reactor._peers[key]
            other_peer_data[key] = {
                'peer-address': str(peer.neighbor.session.peer_address),
                'local-as': peer.neighbor.session.local_as,
            }

        # Delete the target peer (pass matched peer directly)
        result = peer_delete(reactor.api, reactor, 'test-service', [target_peer], '', False)

        assert result is True

        # Verify other peers still exist
        for key in other_peers:
            assert key in reactor._peers
            peer = reactor._peers[key]

            # Verify configuration unchanged
            assert str(peer.neighbor.session.peer_address) == other_peer_data[key]['peer-address']
            assert peer.neighbor.session.local_as == other_peer_data[key]['local-as']

    def test_delete_calls_peer_remove(self, reactor, client):
        """Test that delete calls peer.remove() for graceful TCP teardown."""
        from exabgp.reactor.api.command.peer import peer_delete

        # Get target peer
        all_peers = list(reactor._peers.keys())
        target_peer = [key for key in all_peers if '127.0.0.1' in key][0]
        peer_obj = reactor._peers[target_peer]

        # Delete the peer (pass matched peer directly)
        result = peer_delete(reactor.api, reactor, 'test-service', [target_peer], '', False)

        assert result is True

        # Verify peer.remove() was called (TCP teardown): it stopped the peer for good
        assert peer_obj.stopping()

    def test_delete_removes_key_from_all_structures(self, reactor, client):
        """Test that delete removes peer key from reactor, config, and dynamic tracking."""
        from exabgp.reactor.api.command.peer import peer_delete

        # Get target peer key
        all_peers = list(reactor._peers.keys())
        target_peer = [key for key in all_peers if '127.0.0.2' in key][0]

        # Verify key exists before deletion
        assert target_peer in reactor._peers
        assert target_peer in reactor.configuration.neighbors
        assert target_peer in reactor._dynamic_peers

        # Delete the peer (pass matched peer directly)
        result = peer_delete(reactor.api, reactor, 'test-service', [target_peer], '', False)

        assert result is True

        # Verify key removed from ALL structures
        assert target_peer not in reactor._peers
        assert target_peer not in reactor.configuration.neighbors
        assert target_peer not in reactor._dynamic_peers

    def test_delete_graceful_shutdown_order(self, reactor, client):
        """Test that delete follows correct order: remove() BEFORE deleting from structures.

        remove() stops the peer, which moves its FSM to IDLE and tells the process which
        asked for FSM changes. The client is that process here, so what the reactor holds
        is recorded the moment remove() writes to it.
        """
        from exabgp.reactor.api.command.peer import peer_delete

        # Get target peer
        all_peers = list(reactor._peers.keys())
        target_peer = [key for key in all_peers if '127.0.0.1' in key][0]
        peer_obj = reactor._peers[target_peer]
        peer_obj.neighbor.api['fsm'] = ['test-service']
        reactor.processes._select_encoder('test-service', {'encoder': 'json'})

        # for each line written to the client: was the peer still in the reactor and configuration
        held: list[tuple[bool, bool]] = []
        write = os.write

        def recording(fd: int, data: Any) -> int:
            held.append((target_peer in reactor._peers, target_peer in reactor.configuration.neighbors))
            return write(fd, data)

        # Delete the peer (pass matched peer directly)
        with patch('exabgp.reactor.api.processes.os.write', side_effect=recording):
            result = peer_delete(reactor.api, reactor, 'test-service', [target_peer], '', False)

        assert result is True
        answers = client.lines()
        assert '"state": "IDLE"' in answers[0], 'remove() did not stop the peer'
        assert answers[1:] == ['done']

        # remove() ran while the peer existed in both structures, and the answer after it went
        assert held == [(True, True), (False, False)]

        # Verify peer removed from structures AFTER remove() completed
        assert target_peer not in reactor._peers
