#!/usr/bin/env python3
# encoding: utf-8
"""Comprehensive tests for VPLS (Virtual Private LAN Service) NLRI (RFC 4761/4762)

Created for comprehensive test coverage improvement
"""

from unittest.mock import Mock

from exabgp.bgp.message.direction import Direction
from exabgp.bgp.message.open.capability.negotiated import Negotiated

import pytest
from exabgp.protocol.family import AFI, SAFI
from exabgp.bgp.message import Action
from exabgp.bgp.message.update.nlri.vpls import VPLS
from exabgp.bgp.message.update.nlri.qualifier import RouteDistinguisher
from exabgp.bgp.message.notification import Notify


def create_negotiated() -> Negotiated:
    """Create a Negotiated object with a mock neighbor for testing."""
    neighbor = Mock()
    neighbor.__getitem__ = Mock(return_value={'aigp': False})
    return Negotiated.make_negotiated(neighbor, Direction.OUT)


class TestVPLSCreation:
    """Test basic VPLS route creation"""

    def test_create_vpls_basic(self) -> None:
        """Test creating basic VPLS route"""
        rd = RouteDistinguisher.make_from_elements('172.30.5.4', 13)
        vpls = VPLS.make_vpls(rd, endpoint=3, base=262145, offset=1, size=8)

        assert vpls.afi == AFI.l2vpn
        assert vpls.safi == SAFI.vpls
        assert vpls.rd._str() == rd._str()
        assert vpls.endpoint == 3
        assert vpls.base == 262145
        assert vpls.offset == 1
        assert vpls.block_size == 8
        # Note: action and nexthop are now stored in Route, not NLRI

    def test_create_vpls_various_values(self) -> None:
        """Test creating VPLS with various parameter values"""
        test_cases = [
            (1, 1, 0, 1),
            (100, 500000, 100, 16),
            (65535, 1048575, 65535, 255),  # Max values (20 bits for base)
        ]

        for endpoint, base, offset, size in test_cases:
            rd = RouteDistinguisher.make_from_elements('10.0.0.1', 100)
            vpls = VPLS.make_vpls(rd, endpoint, base, offset, size)

            assert vpls.endpoint == endpoint
            assert vpls.base == base
            assert vpls.offset == offset
            assert vpls.block_size == size


class TestVPLSPackUnpack:
    """Test packing and unpacking VPLS routes"""

    def test_pack_unpack_basic(self) -> None:
        """Test basic pack/unpack roundtrip"""
        rd = RouteDistinguisher.make_from_elements('172.30.5.4', 13)
        vpls = VPLS.make_vpls(rd, endpoint=3, base=262145, offset=1, size=8)

        packed = vpls.pack_nlri(create_negotiated())
        unpacked, leftover = VPLS.unpack_nlri(
            AFI.l2vpn, SAFI.vpls, packed, Action.ANNOUNCE, None, negotiated=create_negotiated()
        )

        assert len(leftover) == 0
        assert isinstance(unpacked, VPLS)
        assert unpacked.endpoint == 3
        assert unpacked.base == 262145
        assert unpacked.offset == 1
        assert unpacked.block_size == 8
        assert unpacked.rd._str() == '172.30.5.4:13'

    def test_pack_unpack_various_values(self) -> None:
        """Test pack/unpack with various values"""
        test_cases = [
            ('10.0.0.1', 1, 1, 1, 0, 1),
            ('192.168.1.1', 100, 100, 500000, 100, 16),
            ('172.16.0.1', 65535, 65535, 1048575, 65535, 255),
        ]

        for ip, rd_num, endpoint, base, offset, size in test_cases:
            rd = RouteDistinguisher.make_from_elements(ip, rd_num)
            vpls = VPLS.make_vpls(rd, endpoint, base, offset, size)

            packed = vpls.pack_nlri(create_negotiated())
            unpacked, leftover = VPLS.unpack_nlri(
                AFI.l2vpn, SAFI.vpls, packed, Action.ANNOUNCE, None, negotiated=create_negotiated()
            )

            assert unpacked.endpoint == endpoint
            assert unpacked.base == base
            assert unpacked.offset == offset
            assert unpacked.block_size == size

    def test_pack_format(self) -> None:
        """Test that pack produces correct format"""
        rd = RouteDistinguisher.make_from_elements('172.30.5.4', 13)
        vpls = VPLS.make_vpls(rd, endpoint=3, base=262145, offset=1, size=8)

        packed = vpls.pack_nlri(create_negotiated())

        # Length should be 2 + 8 (RD) + 2 + 2 + 2 (endpoint, offset, size) + 3 (base with BOS)
        assert len(packed) == 19

        # First 2 bytes should be length (0x0011 = 17 bytes following)
        assert packed[0:2] == b'\x00\x11'

    def test_unpack_requires_exact_length(self) -> None:
        """Test that VPLS unpacking requires exact length match"""
        rd = RouteDistinguisher.make_from_elements('172.30.5.4', 13)
        vpls = VPLS.make_vpls(rd, endpoint=3, base=262145, offset=1, size=8)

        # VPLS requires exact length - extra data causes Notify
        packed = vpls.pack_nlri(create_negotiated()) + b'\x01\x02\x03\x04'

        with pytest.raises(Notify) as exc_info:
            VPLS.unpack_nlri(AFI.l2vpn, SAFI.vpls, packed, Action.ANNOUNCE, None, negotiated=create_negotiated())

        assert 'length is not consistent' in str(exc_info.value)

    def test_unpack_with_action_withdraw(self) -> None:
        """Test unpacking works with withdraw context (action no longer stored in NLRI)"""
        rd = RouteDistinguisher.make_from_elements('172.30.5.4', 13)
        vpls = VPLS.make_vpls(rd, endpoint=3, base=262145, offset=1, size=8)

        packed = vpls.pack_nlri(create_negotiated())
        unpacked, _ = VPLS.unpack_nlri(
            AFI.l2vpn, SAFI.vpls, packed, Action.WITHDRAW, None, negotiated=create_negotiated()
        )

        # Action is no longer stored in NLRI - verify unpack worked correctly
        assert isinstance(unpacked, VPLS)
        assert unpacked.endpoint == 3

    def test_unpack_known_juniper_data(self) -> None:
        """Test unpacking known data from Juniper (from test_l2vpn.py)"""
        # l2vpn:endpoint:3:base:262145:offset:1:size:8: route-distinguisher 172.30.5.4:13
        encoded = bytearray.fromhex('0011 0001 AC1E 0504 000D 0003 0001 0008 4000 11')

        unpacked, leftover = VPLS.unpack_nlri(
            AFI.l2vpn, SAFI.vpls, bytes(encoded), Action.ANNOUNCE, None, negotiated=create_negotiated()
        )

        assert len(leftover) == 0
        assert unpacked.endpoint == 3
        assert unpacked.rd._str() == '172.30.5.4:13'
        assert unpacked.offset == 1
        assert unpacked.base == 262145
        assert unpacked.block_size == 8


class TestVPLSStringRepresentation:
    """Test string representations of VPLS routes"""

    def test_str_vpls(self) -> None:
        """Test string representation"""
        rd = RouteDistinguisher.make_from_elements('172.30.5.4', 13)
        vpls = VPLS.make_vpls(rd, endpoint=3, base=262145, offset=1, size=8)

        result = str(vpls)
        assert 'vpls' in result
        assert '172.30.5.4:13' in result
        assert '3' in result
        assert '262145' in result
        assert '1' in result
        assert '8' in result

    def test_str_vpls_no_nexthop(self) -> None:
        """Test string representation does NOT include nexthop.

        nexthop is not part of NLRI identity - it comes from Route or RoutedNLRI context.
        """
        rd = RouteDistinguisher.make_from_elements('172.30.5.4', 13)
        vpls = VPLS.make_vpls(rd, endpoint=3, base=262145, offset=1, size=8)
        # Note: nexthop is now stored in Route, not NLRI

        result = str(vpls)
        # nexthop is NOT in NLRI.extensive() - comes from Route/RoutedNLRI context
        assert 'next-hop' not in result
        # NLRI identity parts should still be present
        assert 'vpls' in result
        assert 'endpoint' in result

    def test_str_vpls_without_nexthop(self) -> None:
        """Test string representation without nexthop"""
        rd = RouteDistinguisher.make_from_elements('172.30.5.4', 13)
        vpls = VPLS.make_vpls(rd, endpoint=3, base=262145, offset=1, size=8)

        result = str(vpls)
        # Should not contain next-hop when None
        assert result.count('next-hop') == 0 or 'next-hop None' not in result

    def test_extensive(self) -> None:
        """Test extensive method"""
        rd = RouteDistinguisher.make_from_elements('172.30.5.4', 13)
        vpls = VPLS.make_vpls(rd, endpoint=3, base=262145, offset=1, size=8)

        result = vpls.extensive()
        assert 'vpls' in result


class TestVPLSJSON:
    """Test JSON serialization of VPLS routes"""

    def test_json_basic(self) -> None:
        """Test basic JSON serialization"""
        rd = RouteDistinguisher.make_from_elements('172.30.5.4', 13)
        vpls = VPLS.make_vpls(rd, endpoint=3, base=262145, offset=1, size=8)

        json_str = vpls.json()

        assert isinstance(json_str, str)
        assert '{' in json_str
        assert '}' in json_str
        assert '3' in json_str
        assert '262145' in json_str
        assert '1' in json_str
        assert '8' in json_str

    def test_json_contains_rd(self) -> None:
        """Test JSON contains route distinguisher"""
        rd = RouteDistinguisher.make_from_elements('172.30.5.4', 13)
        vpls = VPLS.make_vpls(rd, endpoint=3, base=262145, offset=1, size=8)

        json_str = vpls.json()

        # Should contain RD information
        assert 'route-distinguisher' in json_str or '172.30.5.4' in json_str

    def test_json_contains_all_fields(self) -> None:
        """Test JSON contains all required fields"""
        rd = RouteDistinguisher.make_from_elements('10.0.0.1', 100)
        vpls = VPLS.make_vpls(rd, endpoint=10, base=500000, offset=50, size=16)

        json_str = vpls.json()

        assert '"endpoint": 10' in json_str or '"endpoint":10' in json_str
        assert '"base": 500000' in json_str or '"base":500000' in json_str
        assert '"offset": 50' in json_str or '"offset":50' in json_str
        assert '"size": 16' in json_str or '"size":16' in json_str


class TestVPLSFeedback:
    """Test feedback validation for VPLS routes.

    Note: nexthop validation is now handled by Route.feedback(), not NLRI.feedback().
    NLRI.feedback() only validates NLRI-specific constraints (VPLS has size consistency check).
    """

    def test_nlri_feedback_returns_empty(self) -> None:
        """Test NLRI.feedback() returns empty for valid VPLS"""
        rd = RouteDistinguisher.make_from_elements('172.30.5.4', 13)
        vpls = VPLS.make_vpls(rd, endpoint=3, base=262145, offset=1, size=8)

        # NLRI.feedback() no longer validates nexthop - that's Route's job
        feedback = vpls.feedback(Action.ANNOUNCE)
        assert feedback == ''

    # Note: Tests for missing fields (endpoint, base, offset, size, rd) have been
    # removed because they tested the deprecated builder mode (make_empty + assign).
    # Field validation is now done by VPLSSettings.validate() before NLRI creation.
    # See tests/unit/test_nlri_settings.py for VPLSSettings validation tests.

    def test_feedback_size_inconsistency(self) -> None:
        """Test feedback when base + size exceeds 20-bit limit"""
        rd = RouteDistinguisher.make_from_elements('172.30.5.4', 13)
        # 20 bits max = 0xFFFFF = 1048575
        # If base > (0xFFFFF - size), it's inconsistent
        vpls = VPLS.make_vpls(rd, endpoint=3, base=1048575, offset=1, size=10)

        # VPLS has NLRI-specific validation for size consistency
        feedback = vpls.feedback(Action.ANNOUNCE)
        assert 'vpls nlri size inconsistency' in feedback

    def test_feedback_base_at_limit(self) -> None:
        """Test feedback when base is at the exact limit"""
        rd = RouteDistinguisher.make_from_elements('172.30.5.4', 13)
        # Exactly at limit should pass
        vpls = VPLS.make_vpls(rd, endpoint=3, base=1048567, offset=1, size=8)

        feedback = vpls.feedback(Action.ANNOUNCE)
        assert feedback == ''


# TestVPLSAssign class removed - it tested the deprecated builder mode
# (make_empty + assign). Use VPLSSettings + from_settings() instead.
# See tests/unit/test_nlri_settings.py for Settings pattern tests.


class TestVPLSEdgeCases:
    """Test edge cases for VPLS routes"""

    def test_vpls_minimum_values(self) -> None:
        """Test VPLS with minimum values"""
        rd = RouteDistinguisher.make_from_elements('0.0.0.1', 0)
        vpls = VPLS.make_vpls(rd, endpoint=0, base=0, offset=0, size=0)

        assert vpls.endpoint == 0
        assert vpls.base == 0
        assert vpls.offset == 0
        assert vpls.block_size == 0

    def test_vpls_maximum_base(self) -> None:
        """Test VPLS with maximum 20-bit base value"""
        rd = RouteDistinguisher.make_from_elements('10.0.0.1', 100)
        max_base = 0xFFFFF  # 20 bits = 1048575
        vpls = VPLS.make_vpls(rd, endpoint=1, base=max_base, offset=1, size=0)

        assert vpls.base == max_base

        packed = vpls.pack_nlri(create_negotiated())
        unpacked, _ = VPLS.unpack_nlri(
            AFI.l2vpn, SAFI.vpls, packed, Action.ANNOUNCE, None, negotiated=create_negotiated()
        )

        assert unpacked.base == max_base

    def test_unpack_length_mismatch(self) -> None:
        """Test unpacking with length mismatch raises exception"""
        # Create invalid data with wrong length
        invalid = b'\x00\x10' + b'\x00' * 18  # Says 16 bytes but provides 18

        with pytest.raises(Notify) as exc_info:
            VPLS.unpack_nlri(AFI.l2vpn, SAFI.vpls, invalid, Action.ANNOUNCE, None, negotiated=create_negotiated())

        assert 'length is not consistent' in str(exc_info.value)

    def test_pack_sets_bottom_of_stack(self) -> None:
        """Test that pack_nlri sets the bottom of stack bit"""
        rd = RouteDistinguisher.make_from_elements('172.30.5.4', 13)
        vpls = VPLS.make_vpls(rd, endpoint=3, base=262145, offset=1, size=8)

        packed = vpls.pack_nlri(create_negotiated())

        # The last byte should have bit 0 set (bottom of stack)
        # Base is packed in the last 3 bytes with BOS bit
        last_byte = packed[-1]
        assert last_byte & 0x01 == 0x01


class TestVPLSMultipleRoutes:
    """Test handling multiple VPLS routes"""

    def test_pack_unpack_multiple_separately(self) -> None:
        """Test packing/unpacking multiple VPLS routes (each requires exact length)"""
        routes = [
            VPLS.make_vpls(RouteDistinguisher.make_from_elements('172.30.5.4', 13), 3, 262145, 1, 8),
            VPLS.make_vpls(RouteDistinguisher.make_from_elements('172.30.5.3', 11), 3, 262145, 1, 8),
            VPLS.make_vpls(RouteDistinguisher.make_from_elements('10.0.0.1', 100), 10, 500000, 50, 16),
        ]

        # VPLS requires exact length, so pack and unpack each separately
        for route in routes:
            packed = route.pack_nlri(create_negotiated())
            unpacked, leftover = VPLS.unpack_nlri(
                AFI.l2vpn, SAFI.vpls, packed, Action.ANNOUNCE, None, negotiated=create_negotiated()
            )

            assert len(leftover) == 0
            assert unpacked.rd._str() == route.rd._str()
            assert unpacked.endpoint == route.endpoint
            assert unpacked.base == route.base
            assert unpacked.offset == route.offset
            assert unpacked.block_size == route.block_size

    def test_different_vpls_routes(self) -> None:
        """Test creating and packing different VPLS configurations"""
        configs = [
            ('172.30.5.4', 13, 3, 262145, 1, 8),
            ('172.30.5.3', 11, 3, 262145, 1, 8),
            ('10.0.0.1', 100, 10, 500000, 50, 16),
        ]

        for ip, rd_num, endpoint, base, offset, size in configs:
            rd = RouteDistinguisher.make_from_elements(ip, rd_num)
            vpls = VPLS.make_vpls(rd, endpoint, base, offset, size)

            packed = vpls.pack_nlri(create_negotiated())
            unpacked, _ = VPLS.unpack_nlri(
                AFI.l2vpn, SAFI.vpls, packed, Action.ANNOUNCE, None, negotiated=create_negotiated()
            )

            assert unpacked.rd._str() == f'{ip}:{rd_num}'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
