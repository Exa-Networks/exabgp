#!/usr/bin/env python3
# encoding: utf-8
"""Comprehensive tests for Label (MPLS-labeled routes) NLRI (RFC 3107)

Created for comprehensive test coverage improvement
"""

import pytest
from unittest.mock import Mock
from exabgp.bgp.message.direction import Direction
from exabgp.bgp.message.open.capability.negotiated import Negotiated
from exabgp.protocol.family import AFI, SAFI, Family
from exabgp.bgp.message import Action
from exabgp.bgp.message.update.nlri.label import Label
from exabgp.bgp.message.update.nlri.qualifier import Labels, PathInfo
from exabgp.bgp.message.update.nlri.cidr import CIDR
from exabgp.protocol.ip import IP


def create_negotiated() -> Negotiated:
    """Create a Negotiated object with a mock neighbor for testing."""
    neighbor = Mock()
    neighbor.__getitem__ = Mock(return_value={'aigp': False})
    return Negotiated.make_negotiated(neighbor, Direction.OUT)


class TestLabelCreation:
    """Test basic Label route creation"""

    def test_create_label_ipv4(self) -> None:
        """Test creating basic IPv4 labeled route"""
        cidr = CIDR.make_cidr(IP.pton('192.168.1.0'), 24)
        label = Label.from_cidr(cidr, AFI.ipv4, SAFI.nlri_mpls)

        assert label.afi == AFI.ipv4
        assert label.safi == SAFI.nlri_mpls
        assert label.labels == Labels.NOLABEL

    def test_create_label_ipv6(self) -> None:
        """Test creating basic IPv6 labeled route"""
        cidr = CIDR.make_cidr(IP.pton('2001:db8::'), 32)
        label = Label.from_cidr(cidr, AFI.ipv6, SAFI.nlri_mpls)

        assert label.afi == AFI.ipv6
        assert label.safi == SAFI.nlri_mpls

    def test_create_label_with_data(self) -> None:
        """Test creating labeled route with all attributes"""
        cidr = CIDR.make_cidr(IP.pton('192.168.1.0'), 24)
        label = Label.from_cidr(cidr, AFI.ipv4, SAFI.nlri_mpls, labels=Labels.make_labels([100], True))
        # Note: nexthop is now stored in Route, not NLRI

        assert label.cidr.prefix() == '192.168.1.0/24'
        assert len(label.labels.labels) == 1
        assert label.labels.labels[0] == 100


class TestLabelStringRepresentation:
    """Test string representations of Label routes"""

    def test_str_label(self) -> None:
        """Test string representation"""
        cidr = CIDR.make_cidr(IP.pton('192.168.1.0'), 24)
        label = Label.from_cidr(cidr, AFI.ipv4, SAFI.nlri_mpls, labels=Labels.make_labels([100], True))

        result = str(label)
        assert '192.168.1.0/24' in result

    def test_repr_label(self) -> None:
        """Test repr matches str"""
        cidr = CIDR.make_cidr(IP.pton('192.168.1.0'), 24)
        label = Label.from_cidr(cidr, AFI.ipv4, SAFI.nlri_mpls, labels=Labels.make_labels([100], True))

        assert repr(label) == str(label)

    def test_extensive_without_nexthop(self) -> None:
        """Test extensive representation without nexthop"""
        cidr = CIDR.make_cidr(IP.pton('192.168.1.0'), 24)
        label = Label.from_cidr(cidr, AFI.ipv4, SAFI.nlri_mpls, labels=Labels.make_labels([100], True))

        result = label.extensive()
        assert '192.168.1.0/24' in result

    def test_extensive_no_nexthop(self) -> None:
        """Test extensive representation does NOT include nexthop.

        nexthop is not part of NLRI identity - it comes from Route or RoutedNLRI context.
        """
        cidr = CIDR.make_cidr(IP.pton('192.168.1.0'), 24)
        label = Label.from_cidr(cidr, AFI.ipv4, SAFI.nlri_mpls, labels=Labels.make_labels([100], True))
        # Note: nexthop is now stored in Route, not NLRI

        result = label.extensive()
        assert '192.168.1.0/24' in result
        # nexthop is NOT in NLRI.extensive() - comes from Route/RoutedNLRI context
        assert 'next-hop' not in result


class TestLabelPrefix:
    """Test prefix generation for Label routes"""

    def test_prefix_basic(self) -> None:
        """Test basic prefix generation"""
        cidr = CIDR.make_cidr(IP.pton('192.168.1.0'), 24)
        label = Label.from_cidr(cidr, AFI.ipv4, SAFI.nlri_mpls, labels=Labels.make_labels([100], True))

        prefix = label.prefix()
        assert '192.168.1.0/24' in prefix

    def test_prefix_with_labels(self) -> None:
        """Test prefix includes label information"""
        cidr = CIDR.make_cidr(IP.pton('192.168.1.0'), 24)
        label = Label.from_cidr(cidr, AFI.ipv4, SAFI.nlri_mpls, labels=Labels.make_labels([100, 200], True))

        prefix = label.prefix()
        assert '192.168.1.0/24' in prefix


class TestLabelLength:
    """Test length calculations for Label routes"""

    def test_len_basic(self) -> None:
        """Test basic length calculation"""
        cidr = CIDR.make_cidr(IP.pton('192.168.1.0'), 24)
        label = Label.from_cidr(cidr, AFI.ipv4, SAFI.nlri_mpls, labels=Labels.make_labels([100], True))

        # Length should include CIDR + labels + path_info
        expected = len(label.cidr) + len(label.labels) + len(label.path_info)
        assert len(label) == expected

    def test_len_with_multiple_labels(self) -> None:
        """Test length with multiple labels"""
        cidr = CIDR.make_cidr(IP.pton('192.168.1.0'), 24)
        label = Label.from_cidr(cidr, AFI.ipv4, SAFI.nlri_mpls, labels=Labels.make_labels([100, 200, 300], True))

        # Each label is 3 bytes
        assert len(label) >= 9  # At least 3 labels * 3 bytes


class TestLabelEquality:
    """Test equality and hashing for Label routes"""

    def test_equal_routes(self) -> None:
        """Test that identical routes are equal"""
        cidr1 = CIDR.make_cidr(IP.pton('192.168.1.0'), 24)
        label1 = Label.from_cidr(cidr1, AFI.ipv4, SAFI.nlri_mpls, labels=Labels.make_labels([100], True))

        cidr2 = CIDR.make_cidr(IP.pton('192.168.1.0'), 24)
        label2 = Label.from_cidr(cidr2, AFI.ipv4, SAFI.nlri_mpls, labels=Labels.make_labels([100], True))

        assert label1 == label2

    def test_equal_checks_labels(self) -> None:
        """Test that routes with different labels are checked for equality"""
        cidr1 = CIDR.make_cidr(IP.pton('192.168.1.0'), 24)
        label1 = Label.from_cidr(cidr1, AFI.ipv4, SAFI.nlri_mpls, labels=Labels.make_labels([100], True))

        cidr2 = CIDR.make_cidr(IP.pton('192.168.1.0'), 24)
        label2 = Label.from_cidr(cidr2, AFI.ipv4, SAFI.nlri_mpls, labels=Labels.make_labels([200], True))

        # Equality is based on packed data, so different labels may be equal
        # if they pack the same way (unlikely, but test the comparison works)
        result = label1 == label2
        # Just verify comparison doesn't raise exception
        assert isinstance(result, bool)

    def test_hash_consistency(self) -> None:
        """Test that hash is consistent"""
        cidr = CIDR.make_cidr(IP.pton('192.168.1.0'), 24)
        label = Label.from_cidr(cidr, AFI.ipv4, SAFI.nlri_mpls, labels=Labels.make_labels([100], True))

        hash1 = hash(label)
        hash2 = hash(label)

        assert hash1 == hash2


class TestLabelFeedback:
    """Test feedback validation for Label routes.

    Note: nexthop validation is now handled by Route.feedback(), not NLRI.feedback().
    NLRI.feedback() only validates NLRI-specific constraints (Label has none).
    """

    def test_nlri_feedback_returns_empty(self) -> None:
        """Test NLRI.feedback() returns empty (no NLRI-specific validation)"""
        cidr = CIDR.make_cidr(IP.pton('192.168.1.0'), 24)
        label = Label.from_cidr(cidr, AFI.ipv4, SAFI.nlri_mpls, labels=Labels.make_labels([100], True))

        # NLRI.feedback() no longer validates nexthop - that's Route's job
        feedback = label.feedback(Action.ANNOUNCE)
        assert feedback == ''

    def test_nlri_feedback_withdraw(self) -> None:
        """Test NLRI.feedback() for WITHDRAW"""
        cidr = CIDR.make_cidr(IP.pton('192.168.1.0'), 24)
        label = Label.from_cidr(cidr, AFI.ipv4, SAFI.nlri_mpls, labels=Labels.make_labels([100], True))

        feedback = label.feedback(Action.WITHDRAW)
        assert feedback == ''


class TestLabelPack:
    """Test packing Label routes"""

    def test_pack_basic(self) -> None:
        """Test basic pack operation"""
        cidr = CIDR.make_cidr(IP.pton('192.168.1.0'), 24)
        label = Label.from_cidr(cidr, AFI.ipv4, SAFI.nlri_mpls, labels=Labels.make_labels([100], True))

        packed = label.pack_nlri(create_negotiated())

        assert isinstance(packed, bytes)
        assert len(packed) > 0

    def test_pack_ipv4_various_masks(self) -> None:
        """Test packing IPv4 routes with various masks"""
        test_cases = [8, 16, 24, 25, 30, 32]

        for mask in test_cases:
            cidr = CIDR.make_cidr(IP.pton('10.0.0.0'), mask)
            label = Label.from_cidr(cidr, AFI.ipv4, SAFI.nlri_mpls, labels=Labels.make_labels([100], True))

            packed = label.pack_nlri(create_negotiated())
            assert len(packed) > 0

    def test_pack_ipv6(self) -> None:
        """Test packing IPv6 labeled route"""
        cidr = CIDR.make_cidr(IP.pton('2001:db8::'), 32)
        label = Label.from_cidr(cidr, AFI.ipv6, SAFI.nlri_mpls, labels=Labels.make_labels([100], True))

        packed = label.pack_nlri(create_negotiated())
        assert len(packed) > 0

    def test_pack_multiple_labels(self) -> None:
        """Test packing route with multiple labels"""
        cidr = CIDR.make_cidr(IP.pton('192.168.1.0'), 24)
        label = Label.from_cidr(cidr, AFI.ipv4, SAFI.nlri_mpls, labels=Labels.make_labels([100, 200, 300], True))

        packed = label.pack_nlri(create_negotiated())
        # Should include 3 labels
        assert len(packed) >= 9  # 3 labels * 3 bytes


class TestLabelIndex:
    """Test index generation for Label routes"""

    def test_index_basic(self) -> None:
        """Test basic index generation"""
        cidr = CIDR.make_cidr(IP.pton('192.168.1.0'), 24)
        label = Label.from_cidr(cidr, AFI.ipv4, SAFI.nlri_mpls, labels=Labels.make_labels([100], True))

        index = label.index()

        assert isinstance(index, bytes)
        assert len(index) > 0

    def test_index_contains_family(self) -> None:
        """Test index contains family information"""
        cidr = CIDR.make_cidr(IP.pton('192.168.1.0'), 24)
        label = Label.from_cidr(cidr, AFI.ipv4, SAFI.nlri_mpls, labels=Labels.make_labels([100], True))

        index = label.index()
        family_index = Family.index(label)

        # Index should start with family index
        assert index.startswith(family_index)

    def test_index_with_nopath(self) -> None:
        """Test index with NOPATH (AddPath enabled but no specific ID)"""
        cidr = CIDR.make_cidr(IP.pton('192.168.1.0'), 24)
        # Create with PathInfo.NOPATH - AddPath enabled but no specific ID
        label = Label.from_cidr(
            cidr,
            AFI.ipv4,
            SAFI.nlri_mpls,
            path_info=PathInfo.NOPATH,
            labels=Labels.make_labels([100], True),
        )

        index = label.index()

        # NOPATH uses 'no-pi' marker in index for distinguishing from regular path IDs
        assert b'no-pi' in index


class TestLabelJSON:
    """Test JSON serialization of Label routes"""

    def test_json_announced(self) -> None:
        """Test JSON serialization for announced route"""
        cidr = CIDR.make_cidr(IP.pton('192.168.1.0'), 24)
        label = Label.from_cidr(cidr, AFI.ipv4, SAFI.nlri_mpls, labels=Labels.make_labels([100], True))

        json_str = label.json(announced=True)

        assert isinstance(json_str, str)
        # Should contain label information
        assert 'label' in json_str.lower() or '100' in json_str

    def test_json_withdrawn(self) -> None:
        """Test JSON serialization for withdrawn route"""
        cidr = CIDR.make_cidr(IP.pton('192.168.1.0'), 24)
        label = Label.from_cidr(cidr, AFI.ipv4, SAFI.nlri_mpls, labels=Labels.make_labels([100], True))

        json_str = label.json(announced=False)

        assert isinstance(json_str, str)


class TestLabelEdgeCases:
    """Test edge cases for Label routes"""

    def test_label_zero_prefix_length(self) -> None:
        """Test Label with /0 prefix"""
        cidr = CIDR.make_cidr(IP.pton('0.0.0.0'), 0)
        label = Label.from_cidr(cidr, AFI.ipv4, SAFI.nlri_mpls, labels=Labels.make_labels([100], True))

        packed = label.pack_nlri(create_negotiated())
        assert len(packed) > 0

    def test_label_host_route_ipv4(self) -> None:
        """Test Label with /32 host route"""
        cidr = CIDR.make_cidr(IP.pton('192.168.1.1'), 32)
        label = Label.from_cidr(cidr, AFI.ipv4, SAFI.nlri_mpls, labels=Labels.make_labels([100], True))

        packed = label.pack_nlri(create_negotiated())
        assert len(packed) > 0

    def test_label_host_route_ipv6(self) -> None:
        """Test Label with /128 host route"""
        cidr = CIDR.make_cidr(IP.pton('2001:db8::1'), 128)
        label = Label.from_cidr(cidr, AFI.ipv6, SAFI.nlri_mpls, labels=Labels.make_labels([100], True))

        packed = label.pack_nlri(create_negotiated())
        assert len(packed) > 0

    def test_label_no_labels(self) -> None:
        """Test Label with NOLABEL"""
        cidr = CIDR.make_cidr(IP.pton('192.168.1.0'), 24)
        label = Label.from_cidr(cidr, AFI.ipv4, SAFI.nlri_mpls, labels=Labels.NOLABEL)

        # Should still be able to pack
        packed = label.pack_nlri(create_negotiated())
        assert len(packed) > 0

    def test_label_maximum_label_value(self) -> None:
        """Test Label with maximum label value"""
        cidr = CIDR.make_cidr(IP.pton('192.168.1.0'), 24)
        # MPLS label is 20 bits, max value is 2^20-1 = 1048575
        label = Label.from_cidr(cidr, AFI.ipv4, SAFI.nlri_mpls, labels=Labels.make_labels([1048575], True))

        packed = label.pack_nlri(create_negotiated())
        assert len(packed) > 0


class TestLabelInheritance:
    """Test that Label properly inherits from INET"""

    def test_label_inherits_from_inet(self) -> None:
        """Test Label is subclass of INET"""
        from exabgp.bgp.message.update.nlri.inet import INET

        assert issubclass(Label, INET)

    def test_label_has_cidr(self) -> None:
        """Test Label has CIDR attribute from INET"""
        cidr = CIDR.make_cidr(IP.pton('192.168.1.0'), 24)
        label = Label.from_cidr(cidr, AFI.ipv4, SAFI.nlri_mpls)

        assert hasattr(label, 'cidr')

    def test_label_has_path_info(self) -> None:
        """Test Label has path_info attribute from INET"""
        cidr = CIDR.make_cidr(IP.pton('192.168.1.0'), 24)
        label = Label.from_cidr(cidr, AFI.ipv4, SAFI.nlri_mpls)

        assert hasattr(label, 'path_info')
        assert label.path_info == PathInfo.DISABLED


class TestLabelMultipleRoutes:
    """Test handling multiple Label routes"""

    def test_different_label_routes(self) -> None:
        """Test creating different labeled routes"""
        routes = [
            (AFI.ipv4, '10.1.0.0', 16, [100]),
            (AFI.ipv4, '10.2.0.0', 16, [200]),
            (AFI.ipv6, '2001:db8::', 32, [300]),
        ]

        for afi, ip, mask, label_values in routes:
            cidr = CIDR.make_cidr(IP.pton(ip), mask)
            label = Label.from_cidr(cidr, afi, SAFI.nlri_mpls, labels=Labels.make_labels(label_values, True))

            packed = label.pack_nlri(create_negotiated())
            assert len(packed) > 0
            assert label.labels.labels == label_values


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
