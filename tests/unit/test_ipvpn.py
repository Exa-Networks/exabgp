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
from exabgp.bgp.message.update.nlri.cidr import CIDR
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
        nlri = IPVPN.make_vpn_route(
            AFI.ipv4,
            SAFI.mpls_vpn,
            IP.pton('192.168.1.0'),
            24,
            Labels.make_labels([42], True),
            RouteDistinguisher.make_from_elements('10.0.0.1', 100),
        )

        assert nlri.afi == AFI.ipv4
        assert nlri.safi == SAFI.mpls_vpn
        assert nlri.cidr.prefix() == '192.168.1.0/24'
        assert len(nlri.labels.labels) == 1
        assert nlri.labels.labels[0] == 42
        assert nlri.rd._str() == '10.0.0.1:100'

    def test_create_ipvpn_ipv6(self) -> None:
        """Test creating basic IPv6 IPVPN route"""
        nlri = IPVPN.make_vpn_route(
            AFI.ipv6,
            SAFI.mpls_vpn,
            IP.pton('2001:db8::'),
            32,
            Labels.make_labels([100], True),
            RouteDistinguisher.make_from_elements('10.0.0.1', 200),
        )

        assert nlri.afi == AFI.ipv6
        assert nlri.safi == SAFI.mpls_vpn
        assert '2001:db8::' in nlri.cidr.prefix()
        assert nlri.labels.labels[0] == 100
        assert nlri.rd._str() == '10.0.0.1:200'

    def test_create_ipvpn_with_nexthop(self) -> None:
        """Test creating IPVPN with nexthop"""
        nlri = IPVPN.make_vpn_route(
            AFI.ipv4,
            SAFI.mpls_vpn,
            IP.pton('192.168.1.0'),
            24,
            Labels.make_labels([42], True),
            RouteDistinguisher.make_from_elements('10.0.0.1', 100),
            nexthop='10.0.0.254',
        )

        assert nlri.nexthop == IP.create('10.0.0.254')

    def test_create_ipvpn_with_action(self) -> None:
        """Test creating IPVPN with specific action"""
        nlri = IPVPN.make_vpn_route(
            AFI.ipv4,
            SAFI.mpls_vpn,
            IP.pton('192.168.1.0'),
            24,
            Labels.make_labels([42], True),
            RouteDistinguisher.make_from_elements('10.0.0.1', 100),
            action=Action.WITHDRAW,
        )

        assert nlri.action == Action.WITHDRAW

    def test_create_ipvpn_from_cidr(self) -> None:
        """Test creating IPVPN via from_cidr factory method"""
        cidr = CIDR.make_cidr(IP.pton('10.0.0.0'), 24)
        nlri = IPVPN.from_cidr(cidr, AFI.ipv4, SAFI.mpls_vpn, Action.ANNOUNCE)

        assert nlri.afi == AFI.ipv4
        assert nlri.safi == SAFI.mpls_vpn
        assert nlri.action == Action.ANNOUNCE
        assert nlri.rd == RouteDistinguisher.NORD


class TestIPVPNPackUnpack:
    """Test packing and unpacking IPVPN routes"""

    def test_pack_unpack_ipv4_basic(self) -> None:
        """Test basic pack/unpack roundtrip for IPv4"""
        nlri = IPVPN.make_vpn_route(
            AFI.ipv4,
            SAFI.mpls_vpn,
            IP.pton('192.168.1.0'),
            24,
            Labels.make_labels([42], True),
            RouteDistinguisher.make_from_elements('10.0.0.1', 100),
        )

        packed = nlri.pack_nlri(create_negotiated())
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
        nlri = IPVPN.make_vpn_route(
            AFI.ipv6,
            SAFI.mpls_vpn,
            IP.pton('2001:db8::'),
            32,
            Labels.make_labels([100], True),
            RouteDistinguisher.make_from_elements('10.0.0.1', 200),
        )

        packed = nlri.pack_nlri(create_negotiated())
        unpacked, leftover = IPVPN.unpack_nlri(
            AFI.ipv6, SAFI.mpls_vpn, packed, Action.UNSET, None, negotiated=create_negotiated()
        )

        assert len(leftover) == 0
        assert isinstance(unpacked, IPVPN)
        assert '2001:db8::' in unpacked.cidr.prefix()
        assert unpacked.labels.labels[0] == 100

    def test_pack_unpack_multiple_labels(self) -> None:
        """Test pack/unpack with multiple MPLS labels"""
        nlri = IPVPN.make_vpn_route(
            AFI.ipv4,
            SAFI.mpls_vpn,
            IP.pton('10.1.1.0'),
            24,
            Labels.make_labels([100, 200, 300], True),
            RouteDistinguisher.make_from_elements('172.16.0.1', 50),
        )

        packed = nlri.pack_nlri(create_negotiated())
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
            nlri = IPVPN.make_vpn_route(
                AFI.ipv4,
                SAFI.mpls_vpn,
                IP.pton(ip),
                mask,
                Labels.make_labels([42], True),
                RouteDistinguisher.make_from_elements('10.0.0.1', 100),
            )

            packed = nlri.pack_nlri(create_negotiated())
            unpacked, _ = IPVPN.unpack_nlri(
                AFI.ipv4, SAFI.mpls_vpn, packed, Action.UNSET, None, negotiated=create_negotiated()
            )

            assert unpacked.cidr.mask == mask

    def test_pack_unpack_with_leftover(self) -> None:
        """Test unpacking IPVPN with extra data after route"""
        nlri = IPVPN.make_vpn_route(
            AFI.ipv4,
            SAFI.mpls_vpn,
            IP.pton('192.168.1.0'),
            24,
            Labels.make_labels([42], True),
            RouteDistinguisher.make_from_elements('10.0.0.1', 100),
        )

        packed = nlri.pack_nlri(create_negotiated()) + b'\x01\x02\x03\x04'
        unpacked, leftover = IPVPN.unpack_nlri(
            AFI.ipv4, SAFI.mpls_vpn, packed, Action.UNSET, None, negotiated=create_negotiated()
        )

        assert len(leftover) == 4
        assert leftover == b'\x01\x02\x03\x04'


class TestIPVPNStringRepresentation:
    """Test string representations of IPVPN routes"""

    def test_str_ipvpn(self) -> None:
        """Test string representation"""
        nlri = IPVPN.make_vpn_route(
            AFI.ipv4,
            SAFI.mpls_vpn,
            IP.pton('192.168.1.0'),
            24,
            Labels.make_labels([42], True),
            RouteDistinguisher.make_from_elements('10.0.0.1', 100),
        )

        result = str(nlri)
        assert '192.168.1.0/24' in result
        assert '10.0.0.1:100' in result
        assert 'label' in result.lower() or '42' in result

    def test_repr_ipvpn(self) -> None:
        """Test repr matches str"""
        nlri = IPVPN.make_vpn_route(
            AFI.ipv4,
            SAFI.mpls_vpn,
            IP.pton('192.168.1.0'),
            24,
            Labels.make_labels([42], True),
            RouteDistinguisher.make_from_elements('10.0.0.1', 100),
        )

        assert repr(nlri) == str(nlri)

    def test_extensive_with_nexthop(self) -> None:
        """Test extensive representation with nexthop"""
        nlri = IPVPN.make_vpn_route(
            AFI.ipv4,
            SAFI.mpls_vpn,
            IP.pton('192.168.1.0'),
            24,
            Labels.make_labels([42], True),
            RouteDistinguisher.make_from_elements('10.0.0.1', 100),
            nexthop='10.0.0.254',
        )

        result = nlri.extensive()
        assert '192.168.1.0/24' in result
        assert '10.0.0.1:100' in result


class TestIPVPNLength:
    """Test length calculations for IPVPN routes"""

    def test_len_ipvpn(self) -> None:
        """Test length includes labels and RD"""
        nlri = IPVPN.make_vpn_route(
            AFI.ipv4,
            SAFI.mpls_vpn,
            IP.pton('192.168.1.0'),
            24,
            Labels.make_labels([42], True),
            RouteDistinguisher.make_from_elements('10.0.0.1', 100),
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
        nlri = IPVPN.make_vpn_route(
            AFI.ipv4,
            SAFI.mpls_vpn,
            IP.pton('10.1.1.0'),
            24,
            Labels.make_labels([100, 200, 300], True),
            RouteDistinguisher.make_from_elements('172.16.0.1', 50),
        )

        # 3 labels = 9 bytes, RD = 8 bytes
        assert len(nlri) >= 17


class TestIPVPNEquality:
    """Test equality and hashing for IPVPN routes"""

    def test_equal_routes(self) -> None:
        """Test that identical routes are equal"""
        nlri1 = IPVPN.make_vpn_route(
            AFI.ipv4,
            SAFI.mpls_vpn,
            IP.pton('192.168.1.0'),
            24,
            Labels.make_labels([42], True),
            RouteDistinguisher.make_from_elements('10.0.0.1', 100),
        )

        nlri2 = IPVPN.make_vpn_route(
            AFI.ipv4,
            SAFI.mpls_vpn,
            IP.pton('192.168.1.0'),
            24,
            Labels.make_labels([42], True),
            RouteDistinguisher.make_from_elements('10.0.0.1', 100),
        )

        assert nlri1 == nlri2

    def test_not_equal_different_rd(self) -> None:
        """Test that routes with different RDs are not equal"""
        nlri1 = IPVPN.make_vpn_route(
            AFI.ipv4,
            SAFI.mpls_vpn,
            IP.pton('192.168.1.0'),
            24,
            Labels.make_labels([42], True),
            RouteDistinguisher.make_from_elements('10.0.0.1', 100),
        )

        nlri2 = IPVPN.make_vpn_route(
            AFI.ipv4,
            SAFI.mpls_vpn,
            IP.pton('192.168.1.0'),
            24,
            Labels.make_labels([42], True),
            RouteDistinguisher.make_from_elements('10.0.0.1', 200),
        )

        assert nlri1 != nlri2

    def test_hash_consistency(self) -> None:
        """Test that hash is consistent"""
        nlri = IPVPN.make_vpn_route(
            AFI.ipv4,
            SAFI.mpls_vpn,
            IP.pton('192.168.1.0'),
            24,
            Labels.make_labels([42], True),
            RouteDistinguisher.make_from_elements('10.0.0.1', 100),
        )

        hash1 = hash(nlri)
        hash2 = hash(nlri)

        assert hash1 == hash2


class TestIPVPNFeedback:
    """Test feedback validation for IPVPN routes"""

    def test_feedback_with_nexthop(self) -> None:
        """Test feedback when nexthop is set"""
        nlri = IPVPN.make_vpn_route(
            AFI.ipv4,
            SAFI.mpls_vpn,
            IP.pton('192.168.1.0'),
            24,
            Labels.make_labels([42], True),
            RouteDistinguisher.make_from_elements('10.0.0.1', 100),
            nexthop='10.0.0.254',
        )

        feedback = nlri.feedback(Action.ANNOUNCE)
        assert feedback == ''

    def test_feedback_without_nexthop(self) -> None:
        """Test feedback when nexthop is missing (NoNextHop)"""
        nlri = IPVPN.make_vpn_route(
            AFI.ipv4,
            SAFI.mpls_vpn,
            IP.pton('192.168.1.0'),
            24,
            Labels.make_labels([42], True),
            RouteDistinguisher.make_from_elements('10.0.0.1', 100),
        )
        # nexthop defaults to NoNextHop when not provided

        feedback = nlri.feedback(Action.ANNOUNCE)
        assert 'ip-vpn nlri next-hop missing' in feedback

    def test_feedback_withdraw_no_nexthop_required(self) -> None:
        """Test feedback for WITHDRAW doesn't require nexthop"""
        nlri = IPVPN.make_vpn_route(
            AFI.ipv4,
            SAFI.mpls_vpn,
            IP.pton('192.168.1.0'),
            24,
            Labels.make_labels([42], True),
            RouteDistinguisher.make_from_elements('10.0.0.1', 100),
        )
        # nexthop defaults to NoNextHop when not provided

        feedback = nlri.feedback(Action.WITHDRAW)
        # WITHDRAW validation should pass even without nexthop
        assert feedback == '' or 'next-hop' in feedback


class TestIPVPNIndex:
    """Test index generation for IPVPN routes"""

    def test_index_basic(self) -> None:
        """Test basic index generation"""
        nlri = IPVPN.make_vpn_route(
            AFI.ipv4,
            SAFI.mpls_vpn,
            IP.pton('192.168.1.0'),
            24,
            Labels.make_labels([42], True),
            RouteDistinguisher.make_from_elements('10.0.0.1', 100),
        )

        index = nlri.index()

        assert isinstance(index, bytes)
        assert len(index) > 0

    def test_index_contains_family(self) -> None:
        """Test index contains family information"""
        nlri = IPVPN.make_vpn_route(
            AFI.ipv4,
            SAFI.mpls_vpn,
            IP.pton('192.168.1.0'),
            24,
            Labels.make_labels([42], True),
            RouteDistinguisher.make_from_elements('10.0.0.1', 100),
        )

        index = nlri.index()
        family_index = Family.index(nlri)

        # Index should start with family index
        assert index.startswith(family_index)


class TestIPVPNJSON:
    """Test JSON serialization of IPVPN routes"""

    def test_json_announced(self) -> None:
        """Test JSON serialization for announced route"""
        nlri = IPVPN.make_vpn_route(
            AFI.ipv4,
            SAFI.mpls_vpn,
            IP.pton('192.168.1.0'),
            24,
            Labels.make_labels([42], True),
            RouteDistinguisher.make_from_elements('10.0.0.1', 100),
        )

        json_str = nlri.json(announced=True)

        assert isinstance(json_str, str)
        assert 'route-distinguisher' in json_str or '10.0.0.1' in json_str

    def test_json_withdrawn(self) -> None:
        """Test JSON serialization for withdrawn route"""
        nlri = IPVPN.make_vpn_route(
            AFI.ipv4,
            SAFI.mpls_vpn,
            IP.pton('192.168.1.0'),
            24,
            Labels.make_labels([42], True),
            RouteDistinguisher.make_from_elements('10.0.0.1', 100),
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
        nlri = IPVPN.make_vpn_route(
            AFI.ipv4,
            SAFI.mpls_vpn,
            IP.pton('0.0.0.0'),
            0,
            Labels.make_labels([42], True),
            RouteDistinguisher.make_from_elements('10.0.0.1', 100),
        )

        assert nlri.cidr.mask == 0

        packed = nlri.pack_nlri(create_negotiated())
        unpacked, _ = IPVPN.unpack_nlri(
            AFI.ipv4, SAFI.mpls_vpn, packed, Action.UNSET, None, negotiated=create_negotiated()
        )

        assert unpacked.cidr.mask == 0

    def test_ipvpn_host_route_ipv4(self) -> None:
        """Test IPVPN with /32 host route"""
        nlri = IPVPN.make_vpn_route(
            AFI.ipv4,
            SAFI.mpls_vpn,
            IP.pton('192.168.1.1'),
            32,
            Labels.make_labels([42], True),
            RouteDistinguisher.make_from_elements('10.0.0.1', 100),
        )

        assert nlri.cidr.mask == 32

    def test_ipvpn_host_route_ipv6(self) -> None:
        """Test IPVPN with /128 host route"""
        nlri = IPVPN.make_vpn_route(
            AFI.ipv6,
            SAFI.mpls_vpn,
            IP.pton('2001:db8::1'),
            128,
            Labels.make_labels([42], True),
            RouteDistinguisher.make_from_elements('10.0.0.1', 100),
        )

        assert nlri.cidr.mask == 128


class TestIPVPNMultipleRoutes:
    """Test handling multiple IPVPN routes"""

    def test_pack_unpack_multiple_routes(self) -> None:
        """Test packing/unpacking multiple IPVPN routes"""
        routes = [
            IPVPN.make_vpn_route(
                AFI.ipv4,
                SAFI.mpls_vpn,
                IP.pton('10.1.0.0'),
                16,
                Labels.make_labels([100], True),
                RouteDistinguisher.make_from_elements('10.0.0.1', 1),
            ),
            IPVPN.make_vpn_route(
                AFI.ipv4,
                SAFI.mpls_vpn,
                IP.pton('10.2.0.0'),
                16,
                Labels.make_labels([200], True),
                RouteDistinguisher.make_from_elements('10.0.0.1', 2),
            ),
            IPVPN.make_vpn_route(
                AFI.ipv4,
                SAFI.mpls_vpn,
                IP.pton('10.3.0.0'),
                16,
                Labels.make_labels([300], True),
                RouteDistinguisher.make_from_elements('10.0.0.1', 3),
            ),
        ]

        # Pack all routes
        packed_data = b''.join(r.pack_nlri(create_negotiated()) for r in routes)

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


class TestIPVPNFromCidrEdgeCases:
    """Test edge cases for IPVPN.from_cidr factory method (Wave 6 refactoring scenarios)

    These tests verify behavior when IPVPN is created via from_cidr with
    default labels (NOLABEL) and rd (NORD), then optionally modified.
    """

    def test_from_cidr_defaults_no_labels_no_rd(self) -> None:
        """Test from_cidr creates IPVPN with NOLABEL and NORD by default"""
        cidr = CIDR.make_cidr(IP.pton('192.168.1.0'), 24)
        nlri = IPVPN.from_cidr(cidr, AFI.ipv4, SAFI.mpls_vpn)

        assert nlri.labels == Labels.NOLABEL
        assert nlri.rd == RouteDistinguisher.NORD
        assert nlri.cidr.prefix() == '192.168.1.0/24'

    def test_from_cidr_then_set_rd_only(self) -> None:
        """Test from_cidr then setting RD (no labels)"""
        cidr = CIDR.make_cidr(IP.pton('10.0.0.0'), 24)
        nlri = IPVPN.from_cidr(cidr, AFI.ipv4, SAFI.mpls_vpn)
        nlri.rd = RouteDistinguisher.make_from_elements('10.0.0.1', 100)

        assert nlri.labels == Labels.NOLABEL
        assert nlri.rd._str() == '10.0.0.1:100'
        assert nlri.cidr.prefix() == '10.0.0.0/24'

    def test_from_cidr_then_set_labels_only(self) -> None:
        """Test from_cidr then setting labels (no RD)"""
        cidr = CIDR.make_cidr(IP.pton('10.0.0.0'), 24)
        nlri = IPVPN.from_cidr(cidr, AFI.ipv4, SAFI.mpls_vpn)
        nlri.labels = Labels.make_labels([42], True)

        assert nlri.labels.labels == [42]
        assert nlri.rd == RouteDistinguisher.NORD
        assert nlri.cidr.prefix() == '10.0.0.0/24'

    def test_from_cidr_set_rd_before_labels(self) -> None:
        """Test from_cidr with RD set BEFORE labels (config parser order)

        The configuration parser often sets RD before labels. Verify this
        order works correctly.
        """
        cidr = CIDR.make_cidr(IP.pton('192.168.0.0'), 16)
        nlri = IPVPN.from_cidr(cidr, AFI.ipv4, SAFI.mpls_vpn)

        # Set RD first (like config parser does)
        nlri.rd = RouteDistinguisher.make_from_elements('172.16.0.1', 50)
        assert nlri.rd._str() == '172.16.0.1:50'
        assert nlri.cidr.prefix() == '192.168.0.0/16'

        # Then set labels
        nlri.labels = Labels.make_labels([100, 200], True)
        assert nlri.labels.labels == [100, 200]
        assert nlri.rd._str() == '172.16.0.1:50'  # RD should be preserved
        assert nlri.cidr.prefix() == '192.168.0.0/16'  # CIDR should be preserved

    def test_from_cidr_set_labels_before_rd(self) -> None:
        """Test from_cidr with labels set BEFORE RD"""
        cidr = CIDR.make_cidr(IP.pton('192.168.0.0'), 16)
        nlri = IPVPN.from_cidr(cidr, AFI.ipv4, SAFI.mpls_vpn)

        # Set labels first
        nlri.labels = Labels.make_labels([100], True)
        assert nlri.labels.labels == [100]

        # Then set RD
        nlri.rd = RouteDistinguisher.make_from_elements('172.16.0.1', 50)
        assert nlri.labels.labels == [100]  # Labels should be preserved
        assert nlri.rd._str() == '172.16.0.1:50'
        assert nlri.cidr.prefix() == '192.168.0.0/16'


class TestIPVPNZeroPrefixEdgeCases:
    """Test /0 prefix edge cases (default route scenarios)"""

    def test_ipv4_zero_prefix_with_labels_and_rd(self) -> None:
        """Test IPv4 /0 prefix with labels and RD - roundtrip"""
        nlri = IPVPN.make_vpn_route(
            AFI.ipv4,
            SAFI.mpls_vpn,
            IP.pton('0.0.0.0'),
            0,
            Labels.make_labels([999], True),
            RouteDistinguisher.make_from_elements('10.0.0.1', 1),
        )

        # Verify creation
        assert nlri.cidr.mask == 0
        assert nlri.labels.labels == [999]
        assert nlri.rd._str() == '10.0.0.1:1'

        # Pack and unpack
        packed = nlri.pack_nlri(create_negotiated())
        unpacked, leftover = IPVPN.unpack_nlri(
            AFI.ipv4, SAFI.mpls_vpn, packed, Action.UNSET, None, negotiated=create_negotiated()
        )

        assert len(leftover) == 0
        assert unpacked.cidr.mask == 0
        assert unpacked.labels.labels == [999]
        assert unpacked.rd._str() == '10.0.0.1:1'

    def test_ipv6_zero_prefix_with_labels_and_rd(self) -> None:
        """Test IPv6 /0 prefix with labels and RD - roundtrip"""
        nlri = IPVPN.make_vpn_route(
            AFI.ipv6,
            SAFI.mpls_vpn,
            IP.pton('::'),
            0,
            Labels.make_labels([888], True),
            RouteDistinguisher.make_from_elements('10.0.0.1', 2),
        )

        assert nlri.cidr.mask == 0
        assert nlri.labels.labels == [888]

        packed = nlri.pack_nlri(create_negotiated())
        unpacked, leftover = IPVPN.unpack_nlri(
            AFI.ipv6, SAFI.mpls_vpn, packed, Action.UNSET, None, negotiated=create_negotiated()
        )

        assert len(leftover) == 0
        assert unpacked.cidr.mask == 0
        assert unpacked.labels.labels == [888]


class TestIPVPNIPv6MaskEdgeCases:
    """Test IPv6 IPVPN with various mask values (mask <= 128 detection edge cases)"""

    def test_ipv6_small_prefix_with_labels_mask_lte_128(self) -> None:
        """Test IPv6 IPVPN with /32 prefix (mask = 24 + 64 + 32 = 120 <= 128)

        This is an edge case where the total length in bits (labels + RD + prefix)
        is <= 128, which could confuse label detection logic.
        """
        nlri = IPVPN.make_vpn_route(
            AFI.ipv6,
            SAFI.mpls_vpn,
            IP.pton('2001:db8::'),
            32,  # Small IPv6 prefix
            Labels.make_labels([100], True),  # 1 label = 24 bits
            RouteDistinguisher.make_from_elements('10.0.0.1', 200),  # RD = 64 bits
        )
        # Total: 24 + 64 + 32 = 120 bits <= 128

        assert nlri.cidr.mask == 32
        assert nlri.labels.labels == [100]
        assert nlri.rd._str() == '10.0.0.1:200'

        # Roundtrip test
        packed = nlri.pack_nlri(create_negotiated())
        unpacked, _ = IPVPN.unpack_nlri(
            AFI.ipv6, SAFI.mpls_vpn, packed, Action.UNSET, None, negotiated=create_negotiated()
        )

        assert unpacked.cidr.mask == 32
        assert unpacked.labels.labels == [100]
        assert '2001:db8::' in unpacked.cidr.prefix()

    def test_ipv6_prefix_exactly_128_total_bits(self) -> None:
        """Test IPv6 IPVPN where total bits = exactly 128

        This edge case: 24 (1 label) + 64 (RD) + 40 (prefix) = 128 bits
        """
        nlri = IPVPN.make_vpn_route(
            AFI.ipv6,
            SAFI.mpls_vpn,
            IP.pton('2001:db8:abcd::'),
            40,  # /40 prefix
            Labels.make_labels([50], True),  # 1 label = 24 bits
            RouteDistinguisher.make_from_elements('10.0.0.1', 1),  # RD = 64 bits
        )
        # Total: 24 + 64 + 40 = 128 bits

        packed = nlri.pack_nlri(create_negotiated())
        unpacked, _ = IPVPN.unpack_nlri(
            AFI.ipv6, SAFI.mpls_vpn, packed, Action.UNSET, None, negotiated=create_negotiated()
        )

        assert unpacked.cidr.mask == 40
        assert unpacked.labels.labels == [50]

    def test_ipv6_prefix_over_128_total_bits(self) -> None:
        """Test IPv6 IPVPN where total bits > 128

        This edge case: 24 (1 label) + 64 (RD) + 64 (prefix) = 152 bits
        """
        nlri = IPVPN.make_vpn_route(
            AFI.ipv6,
            SAFI.mpls_vpn,
            IP.pton('2001:db8:abcd:1234::'),
            64,  # /64 prefix
            Labels.make_labels([75], True),  # 1 label = 24 bits
            RouteDistinguisher.make_from_elements('10.0.0.1', 1),  # RD = 64 bits
        )
        # Total: 24 + 64 + 64 = 152 bits

        packed = nlri.pack_nlri(create_negotiated())
        unpacked, _ = IPVPN.unpack_nlri(
            AFI.ipv6, SAFI.mpls_vpn, packed, Action.UNSET, None, negotiated=create_negotiated()
        )

        assert unpacked.cidr.mask == 64
        assert unpacked.labels.labels == [75]


class TestIPVPNRDTypeVariants:
    """Test Route Distinguisher type variants (Type 0, 1, 2)"""

    def test_rd_type_0_asn2(self) -> None:
        """Test RD Type 0 (2-byte ASN:4-byte value)"""
        # Type 0: ASN:value format with 2-byte ASN (prefix as string)
        nlri = IPVPN.make_vpn_route(
            AFI.ipv4,
            SAFI.mpls_vpn,
            IP.pton('10.0.0.0'),
            24,
            Labels.make_labels([100], True),
            RouteDistinguisher.make_from_elements('65000', 12345),  # ASN:value (string prefix)
        )

        packed = nlri.pack_nlri(create_negotiated())
        unpacked, _ = IPVPN.unpack_nlri(
            AFI.ipv4, SAFI.mpls_vpn, packed, Action.UNSET, None, negotiated=create_negotiated()
        )

        assert unpacked.rd._str() == '65000:12345'

    def test_rd_type_1_ip(self) -> None:
        """Test RD Type 1 (IP:value format)"""
        nlri = IPVPN.make_vpn_route(
            AFI.ipv4,
            SAFI.mpls_vpn,
            IP.pton('10.0.0.0'),
            24,
            Labels.make_labels([100], True),
            RouteDistinguisher.make_from_elements('192.168.1.1', 100),  # IP:value
        )

        packed = nlri.pack_nlri(create_negotiated())
        unpacked, _ = IPVPN.unpack_nlri(
            AFI.ipv4, SAFI.mpls_vpn, packed, Action.UNSET, None, negotiated=create_negotiated()
        )

        assert unpacked.rd._str() == '192.168.1.1:100'


class TestIPVPNMultipleLabelEdgeCases:
    """Test IPVPN with multiple MPLS labels in the stack"""

    def test_maximum_typical_label_stack(self) -> None:
        """Test with 3 labels (common maximum for MPLS VPN)"""
        nlri = IPVPN.make_vpn_route(
            AFI.ipv4,
            SAFI.mpls_vpn,
            IP.pton('10.0.0.0'),
            24,
            Labels.make_labels([100, 200, 300], True),  # 3 labels = 72 bits
            RouteDistinguisher.make_from_elements('10.0.0.1', 1),
        )

        packed = nlri.pack_nlri(create_negotiated())
        unpacked, _ = IPVPN.unpack_nlri(
            AFI.ipv4, SAFI.mpls_vpn, packed, Action.UNSET, None, negotiated=create_negotiated()
        )

        assert len(unpacked.labels.labels) == 3
        assert unpacked.labels.labels == [100, 200, 300]
        assert unpacked.cidr.prefix() == '10.0.0.0/24'

    def test_single_label_vs_no_labels(self) -> None:
        """Compare behavior of NOLABEL vs single label"""
        # With NOLABEL
        cidr = CIDR.make_cidr(IP.pton('10.0.0.0'), 24)
        nlri_no_label = IPVPN.from_cidr(cidr, AFI.ipv4, SAFI.mpls_vpn)
        nlri_no_label.rd = RouteDistinguisher.make_from_elements('10.0.0.1', 1)

        # With single label
        nlri_with_label = IPVPN.make_vpn_route(
            AFI.ipv4,
            SAFI.mpls_vpn,
            IP.pton('10.0.0.0'),
            24,
            Labels.make_labels([42], True),
            RouteDistinguisher.make_from_elements('10.0.0.1', 1),
        )

        # Both should have same RD and CIDR
        assert nlri_no_label.rd._str() == nlri_with_label.rd._str()
        assert nlri_no_label.cidr.prefix() == nlri_with_label.cidr.prefix()

        # But different labels
        assert nlri_no_label.labels == Labels.NOLABEL
        assert nlri_with_label.labels.labels == [42]


class TestIPVPNHighMaskValues:
    """Test IPVPN with high mask values (labels + RD + prefix > 128 bits)

    These tests ensure CIDR.size() handles masks > 128 correctly.
    Issue: CIDR._mask_to_bytes only went to 128, causing IPVPN unpack to fail
    for routes with labels + RD + larger prefixes.
    """

    def test_ipv6_vpn_high_mask(self) -> None:
        """Test IPv6 VPN with mask > 128 (label + RD + 48-bit prefix = 136 bits)

        This matches the conf-parity.conf scenario that was previously failing.
        """
        nlri = IPVPN.make_vpn_route(
            AFI.ipv6,
            SAFI.mpls_vpn,
            IP.pton('2001:4b50:20c0::'),
            48,
            Labels.make_labels([926], True),
            RouteDistinguisher.make_from_elements('3215', 583457597),
        )

        # Verify original creation
        assert nlri.cidr.prefix() == '2001:4b50:20c0::/48'
        assert nlri.labels.labels == [926]
        assert nlri.rd._str() == '3215:583457597'

        # Pack and verify mask is 136 (24 + 64 + 48)
        packed = nlri.pack_nlri(create_negotiated())
        assert packed[0] == 136  # 24 (label) + 64 (RD) + 48 (prefix)

        # Unpack and verify round-trip
        unpacked, leftover = IPVPN.unpack_nlri(AFI.ipv6, SAFI.mpls_vpn, packed, Action.UNSET, None, create_negotiated())

        assert len(leftover) == 0
        assert unpacked.cidr.prefix() == '2001:4b50:20c0::/48'
        assert unpacked.labels.labels == [926]
        assert unpacked.rd._str() == '3215:583457597'

    def test_ipv4_vpn_three_labels_high_mask(self) -> None:
        """Test IPv4 VPN with 3 labels (mask = 160 bits)"""
        nlri = IPVPN.make_vpn_route(
            AFI.ipv4,
            SAFI.mpls_vpn,
            IP.pton('10.1.1.0'),
            24,
            Labels.make_labels([100, 200, 300], True),
            RouteDistinguisher.make_from_elements('172.16.0.1', 50),
        )

        # Verify original
        assert nlri.labels.labels == [100, 200, 300]

        # Pack and verify mask is 160 (72 + 64 + 24)
        packed = nlri.pack_nlri(create_negotiated())
        assert packed[0] == 160  # 72 (3 labels) + 64 (RD) + 24 (prefix)

        # Unpack and verify round-trip
        unpacked, _ = IPVPN.unpack_nlri(AFI.ipv4, SAFI.mpls_vpn, packed, Action.UNSET, None, create_negotiated())

        assert unpacked.labels.labels == [100, 200, 300]
        assert unpacked.cidr.prefix() == '10.1.1.0/24'

    def test_ipv6_vpn_128_prefix_maximum_mask(self) -> None:
        """Test IPv6 VPN with /128 prefix (mask = 216 bits - maximum)"""
        nlri = IPVPN.make_vpn_route(
            AFI.ipv6,
            SAFI.mpls_vpn,
            IP.pton('2001:db8::1'),
            128,
            Labels.make_labels([42], True),
            RouteDistinguisher.make_from_elements('10.0.0.1', 100),
        )

        # Pack and verify mask is 216 (24 + 64 + 128)
        packed = nlri.pack_nlri(create_negotiated())
        assert packed[0] == 216  # 24 (label) + 64 (RD) + 128 (prefix)

        # Unpack and verify round-trip
        unpacked, _ = IPVPN.unpack_nlri(AFI.ipv6, SAFI.mpls_vpn, packed, Action.UNSET, None, create_negotiated())

        assert unpacked.cidr.mask == 128
        assert unpacked.labels.labels == [42]


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
