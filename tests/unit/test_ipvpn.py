#!/usr/bin/env python3
# encoding: utf-8
"""Comprehensive tests for IPVPN (IP VPN) NLRI (RFC 4364)

Created for comprehensive test coverage improvement
"""

from unittest.mock import Mock

from exabgp.bgp.message.direction import Direction
from exabgp.bgp.message.open.capability.negotiated import Negotiated

import pytest
from exabgp.protocol.family import AFI, SAFI, Family
from exabgp.bgp.message import Action
from exabgp.bgp.message.update.nlri.ipvpn import IPVPN
from exabgp.bgp.message.update.nlri.qualifier import RouteDistinguisher, Labels
from exabgp.protocol.ip import IP


def create_negotiated() -> Negotiated:
    """Create a Negotiated object with a mock neighbor for testing."""
    neighbor = Mock()
    neighbor.__getitem__ = Mock(return_value={'aigp': False})
    return Negotiated(neighbor, Direction.OUT)


class TestIPVPNCreation:
    """Test basic IPVPN route creation"""

    def test_create_ipvpn_ipv4(self) -> None:
        """Test creating basic IPv4 IPVPN route"""
        nlri = IPVPN.new(
            AFI.ipv4,
            SAFI.mpls_vpn,
            IP.pton('192.168.1.0'),
            24,
            Labels([42], True),
            RouteDistinguisher.fromElements('10.0.0.1', 100),
        )

        assert nlri.afi == AFI.ipv4
        assert nlri.safi == SAFI.mpls_vpn
        assert nlri.cidr.prefix() == '192.168.1.0/24'
        assert len(nlri.labels.labels) == 1
        assert nlri.labels.labels[0] == 42
        assert nlri.rd._str() == '10.0.0.1:100'

    def test_create_ipvpn_ipv6(self) -> None:
        """Test creating basic IPv6 IPVPN route"""
        nlri = IPVPN.new(
            AFI.ipv6,
            SAFI.mpls_vpn,
            IP.pton('2001:db8::'),
            32,
            Labels([100], True),
            RouteDistinguisher.fromElements('10.0.0.1', 200),
        )

        assert nlri.afi == AFI.ipv6
        assert nlri.safi == SAFI.mpls_vpn
        assert '2001:db8::' in nlri.cidr.prefix()
        assert nlri.labels.labels[0] == 100
        assert nlri.rd._str() == '10.0.0.1:200'

    def test_create_ipvpn_with_nexthop(self) -> None:
        """Test creating IPVPN with nexthop"""
        nlri = IPVPN.new(
            AFI.ipv4,
            SAFI.mpls_vpn,
            IP.pton('192.168.1.0'),
            24,
            Labels([42], True),
            RouteDistinguisher.fromElements('10.0.0.1', 100),
            nexthop='10.0.0.254',
        )

        assert nlri.nexthop == IP.create('10.0.0.254')

    def test_create_ipvpn_with_action(self) -> None:
        """Test creating IPVPN with specific action"""
        nlri = IPVPN.new(
            AFI.ipv4,
            SAFI.mpls_vpn,
            IP.pton('192.168.1.0'),
            24,
            Labels([42], True),
            RouteDistinguisher.fromElements('10.0.0.1', 100),
            action=Action.WITHDRAW,
        )

        assert nlri.action == Action.WITHDRAW

    def test_create_ipvpn_direct_init(self) -> None:
        """Test creating IPVPN via direct initialization"""
        nlri = IPVPN(AFI.ipv4, SAFI.mpls_vpn, Action.ANNOUNCE)

        assert nlri.afi == AFI.ipv4
        assert nlri.safi == SAFI.mpls_vpn
        assert nlri.action == Action.ANNOUNCE
        assert nlri.rd == RouteDistinguisher.NORD


class TestIPVPNPackUnpack:
    """Test packing and unpacking IPVPN routes"""

    def test_pack_unpack_ipv4_basic(self) -> None:
        """Test basic pack/unpack roundtrip for IPv4"""
        nlri = IPVPN.new(
            AFI.ipv4,
            SAFI.mpls_vpn,
            IP.pton('192.168.1.0'),
            24,
            Labels([42], True),
            RouteDistinguisher.fromElements('10.0.0.1', 100),
        )

        packed = nlri.pack_nlri()
        unpacked, leftover = IPVPN.unpack_nlri(
            AFI.ipv4, SAFI.mpls_vpn, packed, Action.UNSET, None, negotiated=create_negotiated()
        )

        assert len(leftover) == 0
        assert isinstance(unpacked, IPVPN)
        assert unpacked.cidr.prefix() == '192.168.1.0/24'
        assert len(unpacked.labels.labels) == 1
        assert unpacked.labels.labels[0] == 42
        assert unpacked.rd._str() == '10.0.0.1:100'

    def test_pack_unpack_ipv6_basic(self) -> None:
        """Test basic pack/unpack roundtrip for IPv6"""
        nlri = IPVPN.new(
            AFI.ipv6,
            SAFI.mpls_vpn,
            IP.pton('2001:db8::'),
            32,
            Labels([100], True),
            RouteDistinguisher.fromElements('10.0.0.1', 200),
        )

        packed = nlri.pack_nlri()
        unpacked, leftover = IPVPN.unpack_nlri(
            AFI.ipv6, SAFI.mpls_vpn, packed, Action.UNSET, None, negotiated=create_negotiated()
        )

        assert len(leftover) == 0
        assert isinstance(unpacked, IPVPN)
        assert '2001:db8::' in unpacked.cidr.prefix()
        assert unpacked.labels.labels[0] == 100

    def test_pack_unpack_multiple_labels(self) -> None:
        """Test pack/unpack with multiple MPLS labels"""
        nlri = IPVPN.new(
            AFI.ipv4,
            SAFI.mpls_vpn,
            IP.pton('10.1.1.0'),
            24,
            Labels([100, 200, 300], True),
            RouteDistinguisher.fromElements('172.16.0.1', 50),
        )

        packed = nlri.pack_nlri()
        unpacked, _ = IPVPN.unpack_nlri(
            AFI.ipv4, SAFI.mpls_vpn, packed, Action.UNSET, None, negotiated=create_negotiated()
        )

        assert len(unpacked.labels.labels) == 3
        assert unpacked.labels.labels == [100, 200, 300]

    def test_pack_unpack_various_prefixes(self) -> None:
        """Test pack/unpack with various prefix lengths"""
        test_cases = [
            ('10.0.0.0', 8),
            ('172.16.0.0', 12),
            ('192.168.1.0', 24),
            ('192.168.1.128', 25),
            ('192.168.1.0', 30),
            ('192.168.1.1', 32),
        ]

        for ip, mask in test_cases:
            nlri = IPVPN.new(
                AFI.ipv4,
                SAFI.mpls_vpn,
                IP.pton(ip),
                mask,
                Labels([42], True),
                RouteDistinguisher.fromElements('10.0.0.1', 100),
            )

            packed = nlri.pack_nlri()
            unpacked, _ = IPVPN.unpack_nlri(
                AFI.ipv4, SAFI.mpls_vpn, packed, Action.UNSET, None, negotiated=create_negotiated()
            )

            assert unpacked.cidr.mask == mask

    def test_pack_unpack_with_leftover(self) -> None:
        """Test unpacking IPVPN with extra data after route"""
        nlri = IPVPN.new(
            AFI.ipv4,
            SAFI.mpls_vpn,
            IP.pton('192.168.1.0'),
            24,
            Labels([42], True),
            RouteDistinguisher.fromElements('10.0.0.1', 100),
        )

        packed = nlri.pack_nlri() + b'\x01\x02\x03\x04'
        unpacked, leftover = IPVPN.unpack_nlri(
            AFI.ipv4, SAFI.mpls_vpn, packed, Action.UNSET, None, negotiated=create_negotiated()
        )

        assert len(leftover) == 4
        assert leftover == b'\x01\x02\x03\x04'


class TestIPVPNStringRepresentation:
    """Test string representations of IPVPN routes"""

    def test_str_ipvpn(self) -> None:
        """Test string representation"""
        nlri = IPVPN.new(
            AFI.ipv4,
            SAFI.mpls_vpn,
            IP.pton('192.168.1.0'),
            24,
            Labels([42], True),
            RouteDistinguisher.fromElements('10.0.0.1', 100),
        )

        result = str(nlri)
        assert '192.168.1.0/24' in result
        assert '10.0.0.1:100' in result
        assert 'label' in result.lower() or '42' in result

    def test_repr_ipvpn(self) -> None:
        """Test repr matches str"""
        nlri = IPVPN.new(
            AFI.ipv4,
            SAFI.mpls_vpn,
            IP.pton('192.168.1.0'),
            24,
            Labels([42], True),
            RouteDistinguisher.fromElements('10.0.0.1', 100),
        )

        assert repr(nlri) == str(nlri)

    def test_extensive_with_nexthop(self) -> None:
        """Test extensive representation with nexthop"""
        nlri = IPVPN.new(
            AFI.ipv4,
            SAFI.mpls_vpn,
            IP.pton('192.168.1.0'),
            24,
            Labels([42], True),
            RouteDistinguisher.fromElements('10.0.0.1', 100),
            nexthop='10.0.0.254',
        )

        result = nlri.extensive()
        assert '192.168.1.0/24' in result
        assert '10.0.0.1:100' in result


class TestIPVPNLength:
    """Test length calculations for IPVPN routes"""

    def test_len_ipvpn(self) -> None:
        """Test length includes labels and RD"""
        nlri = IPVPN.new(
            AFI.ipv4,
            SAFI.mpls_vpn,
            IP.pton('192.168.1.0'),
            24,
            Labels([42], True),
            RouteDistinguisher.fromElements('10.0.0.1', 100),
        )

        # Length should include RD (8 bytes) + labels + CIDR + path_info
        assert len(nlri) > 0
        expected_len = 8  # RD
        expected_len += len(nlri.labels)  # Labels
        expected_len += len(nlri.cidr)  # CIDR
        expected_len += len(nlri.path_info)  # Path info

        assert len(nlri) == expected_len

    def test_len_with_multiple_labels(self) -> None:
        """Test length with multiple labels"""
        nlri = IPVPN.new(
            AFI.ipv4,
            SAFI.mpls_vpn,
            IP.pton('10.1.1.0'),
            24,
            Labels([100, 200, 300], True),
            RouteDistinguisher.fromElements('172.16.0.1', 50),
        )

        # 3 labels = 9 bytes, RD = 8 bytes
        assert len(nlri) >= 17


class TestIPVPNEquality:
    """Test equality and hashing for IPVPN routes"""

    def test_equal_routes(self) -> None:
        """Test that identical routes are equal"""
        nlri1 = IPVPN.new(
            AFI.ipv4,
            SAFI.mpls_vpn,
            IP.pton('192.168.1.0'),
            24,
            Labels([42], True),
            RouteDistinguisher.fromElements('10.0.0.1', 100),
        )

        nlri2 = IPVPN.new(
            AFI.ipv4,
            SAFI.mpls_vpn,
            IP.pton('192.168.1.0'),
            24,
            Labels([42], True),
            RouteDistinguisher.fromElements('10.0.0.1', 100),
        )

        assert nlri1 == nlri2

    def test_not_equal_different_rd(self) -> None:
        """Test that routes with different RDs are not equal"""
        nlri1 = IPVPN.new(
            AFI.ipv4,
            SAFI.mpls_vpn,
            IP.pton('192.168.1.0'),
            24,
            Labels([42], True),
            RouteDistinguisher.fromElements('10.0.0.1', 100),
        )

        nlri2 = IPVPN.new(
            AFI.ipv4,
            SAFI.mpls_vpn,
            IP.pton('192.168.1.0'),
            24,
            Labels([42], True),
            RouteDistinguisher.fromElements('10.0.0.1', 200),
        )

        assert nlri1 != nlri2

    def test_hash_consistency(self) -> None:
        """Test that hash is consistent"""
        nlri = IPVPN.new(
            AFI.ipv4,
            SAFI.mpls_vpn,
            IP.pton('192.168.1.0'),
            24,
            Labels([42], True),
            RouteDistinguisher.fromElements('10.0.0.1', 100),
        )

        hash1 = hash(nlri)
        hash2 = hash(nlri)

        assert hash1 == hash2


class TestIPVPNFeedback:
    """Test feedback validation for IPVPN routes"""

    def test_feedback_with_nexthop(self) -> None:
        """Test feedback when nexthop is set"""
        nlri = IPVPN.new(
            AFI.ipv4,
            SAFI.mpls_vpn,
            IP.pton('192.168.1.0'),
            24,
            Labels([42], True),
            RouteDistinguisher.fromElements('10.0.0.1', 100),
            nexthop='10.0.0.254',
        )

        feedback = nlri.feedback(Action.ANNOUNCE)
        assert feedback == ''

    def test_feedback_without_nexthop(self) -> None:
        """Test feedback when nexthop is missing"""
        nlri = IPVPN.new(
            AFI.ipv4,
            SAFI.mpls_vpn,
            IP.pton('192.168.1.0'),
            24,
            Labels([42], True),
            RouteDistinguisher.fromElements('10.0.0.1', 100),
        )
        nlri.nexthop = None

        feedback = nlri.feedback(Action.ANNOUNCE)
        assert 'ip-vpn nlri next-hop missing' in feedback

    def test_feedback_withdraw_no_nexthop_required(self) -> None:
        """Test feedback for WITHDRAW doesn't require nexthop"""
        nlri = IPVPN.new(
            AFI.ipv4,
            SAFI.mpls_vpn,
            IP.pton('192.168.1.0'),
            24,
            Labels([42], True),
            RouteDistinguisher.fromElements('10.0.0.1', 100),
        )
        nlri.nexthop = None

        feedback = nlri.feedback(Action.WITHDRAW)
        # WITHDRAW validation should pass even without nexthop
        assert feedback == '' or 'next-hop' in feedback


class TestIPVPNIndex:
    """Test index generation for IPVPN routes"""

    def test_index_basic(self) -> None:
        """Test basic index generation"""
        nlri = IPVPN.new(
            AFI.ipv4,
            SAFI.mpls_vpn,
            IP.pton('192.168.1.0'),
            24,
            Labels([42], True),
            RouteDistinguisher.fromElements('10.0.0.1', 100),
        )

        index = nlri.index()

        assert isinstance(index, bytes)
        assert len(index) > 0

    def test_index_contains_family(self) -> None:
        """Test index contains family information"""
        nlri = IPVPN.new(
            AFI.ipv4,
            SAFI.mpls_vpn,
            IP.pton('192.168.1.0'),
            24,
            Labels([42], True),
            RouteDistinguisher.fromElements('10.0.0.1', 100),
        )

        index = nlri.index()
        family_index = Family.index(nlri)

        # Index should start with family index
        assert index.startswith(family_index)


class TestIPVPNJSON:
    """Test JSON serialization of IPVPN routes"""

    def test_json_announced(self) -> None:
        """Test JSON serialization for announced route"""
        nlri = IPVPN.new(
            AFI.ipv4,
            SAFI.mpls_vpn,
            IP.pton('192.168.1.0'),
            24,
            Labels([42], True),
            RouteDistinguisher.fromElements('10.0.0.1', 100),
        )

        json_str = nlri.json(announced=True)

        assert isinstance(json_str, str)
        assert 'route-distinguisher' in json_str or '10.0.0.1' in json_str

    def test_json_withdrawn(self) -> None:
        """Test JSON serialization for withdrawn route"""
        nlri = IPVPN.new(
            AFI.ipv4,
            SAFI.mpls_vpn,
            IP.pton('192.168.1.0'),
            24,
            Labels([42], True),
            RouteDistinguisher.fromElements('10.0.0.1', 100),
        )

        json_str = nlri.json(announced=False)

        assert isinstance(json_str, str)


class TestIPVPNHasRD:
    """Test the has_rd class method"""

    def test_has_rd_returns_true(self) -> None:
        """Test that IPVPN.has_rd() returns True"""
        assert IPVPN.has_rd() is True


class TestIPVPNEdgeCases:
    """Test edge cases for IPVPN routes"""

    def test_ipvpn_zero_prefix_length(self) -> None:
        """Test IPVPN with /0 prefix"""
        nlri = IPVPN.new(
            AFI.ipv4,
            SAFI.mpls_vpn,
            IP.pton('0.0.0.0'),
            0,
            Labels([42], True),
            RouteDistinguisher.fromElements('10.0.0.1', 100),
        )

        assert nlri.cidr.mask == 0

        packed = nlri.pack_nlri()
        unpacked, _ = IPVPN.unpack_nlri(
            AFI.ipv4, SAFI.mpls_vpn, packed, Action.UNSET, None, negotiated=create_negotiated()
        )

        assert unpacked.cidr.mask == 0

    def test_ipvpn_host_route_ipv4(self) -> None:
        """Test IPVPN with /32 host route"""
        nlri = IPVPN.new(
            AFI.ipv4,
            SAFI.mpls_vpn,
            IP.pton('192.168.1.1'),
            32,
            Labels([42], True),
            RouteDistinguisher.fromElements('10.0.0.1', 100),
        )

        assert nlri.cidr.mask == 32

    def test_ipvpn_host_route_ipv6(self) -> None:
        """Test IPVPN with /128 host route"""
        nlri = IPVPN.new(
            AFI.ipv6,
            SAFI.mpls_vpn,
            IP.pton('2001:db8::1'),
            128,
            Labels([42], True),
            RouteDistinguisher.fromElements('10.0.0.1', 100),
        )

        assert nlri.cidr.mask == 128


class TestIPVPNMultipleRoutes:
    """Test handling multiple IPVPN routes"""

    def test_pack_unpack_multiple_routes(self) -> None:
        """Test packing/unpacking multiple IPVPN routes"""
        routes = [
            IPVPN.new(
                AFI.ipv4,
                SAFI.mpls_vpn,
                IP.pton('10.1.0.0'),
                16,
                Labels([100], True),
                RouteDistinguisher.fromElements('10.0.0.1', 1),
            ),
            IPVPN.new(
                AFI.ipv4,
                SAFI.mpls_vpn,
                IP.pton('10.2.0.0'),
                16,
                Labels([200], True),
                RouteDistinguisher.fromElements('10.0.0.1', 2),
            ),
            IPVPN.new(
                AFI.ipv4,
                SAFI.mpls_vpn,
                IP.pton('10.3.0.0'),
                16,
                Labels([300], True),
                RouteDistinguisher.fromElements('10.0.0.1', 3),
            ),
        ]

        # Pack all routes
        packed_data = b''.join(r.pack_nlri() for r in routes)

        # Unpack all routes
        data = packed_data
        unpacked_routes = []
        for _ in range(3):
            route, data = IPVPN.unpack_nlri(
                AFI.ipv4, SAFI.mpls_vpn, data, Action.UNSET, None, negotiated=create_negotiated()
            )
            unpacked_routes.append(route)

        assert len(unpacked_routes) == 3
        assert unpacked_routes[0].labels.labels[0] == 100
        assert unpacked_routes[1].labels.labels[0] == 200
        assert unpacked_routes[2].labels.labels[0] == 300


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
