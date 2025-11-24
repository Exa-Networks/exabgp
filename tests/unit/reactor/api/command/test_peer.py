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
