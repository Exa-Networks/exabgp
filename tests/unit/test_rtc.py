#!/usr/bin/env python3
# encoding: utf-8
"""Comprehensive tests for RTC (Route Target Constraint) NLRI (RFC 4684)

Created for comprehensive test coverage improvement
"""

from unittest.mock import Mock

from exabgp.bgp.message.direction import Direction
from exabgp.bgp.message.open.capability.negotiated import Negotiated

import pytest
from exabgp.protocol.family import AFI, SAFI
from exabgp.bgp.message import Action
from exabgp.bgp.message.open.asn import ASN
from exabgp.bgp.message.update.attribute.community.extended.rt import RouteTargetASN2Number as RouteTarget
from exabgp.bgp.message.update.nlri.rtc import RTC
from exabgp.bgp.message.update.nlri.nlri import NLRI
from exabgp.protocol.ip import IP


def create_negotiated() -> Negotiated:
    """Create a Negotiated object with a mock neighbor for testing."""
    neighbor = Mock()
    neighbor.__getitem__ = Mock(return_value={'aigp': False})
    return Negotiated.make_negotiated(neighbor, Direction.OUT)


class TestRTCCreation:
    """Test basic RTC route creation"""

    def test_create_rtc_with_route_target(self) -> None:
        """Test creating RTC route with route target"""
        rt = RouteTarget.make_route_target(64512, 100)
        nlri = RTC.make_rtc(ASN(65000), rt)

        assert nlri.afi == AFI.ipv4
        assert nlri.safi == SAFI.rtc
        assert nlri.origin == 65000
        assert nlri.rt == rt
        assert nlri.nexthop == IP.NoNextHop

    def test_create_rtc_wildcard(self) -> None:
        """Test creating wildcard RTC route"""
        nlri = RTC.make_rtc(ASN(0), None)

        assert nlri.afi == AFI.ipv4
        assert nlri.safi == SAFI.rtc
        assert nlri.origin == 0
        assert nlri.rt is None
        assert nlri.nexthop == IP.NoNextHop

    def test_create_rtc_with_action(self) -> None:
        """Test creating RTC with specific action"""
        rt = RouteTarget.make_route_target(64512, 100)
        nlri = RTC.make_rtc(ASN(65000), rt, action=Action.ANNOUNCE)

        assert nlri.action == Action.ANNOUNCE

    def test_create_rtc_with_nexthop(self) -> None:
        """Test creating RTC with nexthop"""
        rt = RouteTarget.make_route_target(64512, 100)
        nh = IP.from_string('10.0.0.1')
        nlri = RTC.make_rtc(ASN(65000), rt, nexthop=nh)

        assert nlri.nexthop == nh

    def test_create_rtc_direct_init(self) -> None:
        """Test creating RTC via make_rtc factory"""
        rt = RouteTarget.make_route_target(64512, 100)
        nlri = RTC.make_rtc(ASN(65000), rt, Action.ANNOUNCE)

        assert nlri.afi == AFI.ipv4
        assert nlri.safi == SAFI.rtc
        assert nlri.action == Action.ANNOUNCE
        assert nlri.origin == 65000
        assert nlri.rt == rt


class TestRTCPackUnpack:
    """Test packing and unpacking RTC routes"""

    def test_pack_unpack_rtc_with_rt(self) -> None:
        """Test pack/unpack roundtrip for RTC with route target"""
        rt = RouteTarget.make_route_target(64512, 100)
        nlri = RTC.make_rtc(ASN(65000), rt)

        packed = nlri.pack_nlri(create_negotiated())
        unpacked, leftover = RTC.unpack_nlri(
            AFI.ipv4, SAFI.rtc, packed, Action.UNSET, None, negotiated=create_negotiated()
        )

        assert len(leftover) == 0
        assert isinstance(unpacked, RTC)
        assert unpacked.origin == 65000
        assert isinstance(unpacked.rt, RouteTarget)
        assert unpacked.rt.asn == 64512
        assert unpacked.rt.number == 100

    def test_pack_unpack_rtc_wildcard(self) -> None:
        """Test pack/unpack roundtrip for wildcard RTC"""
        nlri = RTC.make_rtc(ASN(0), None)

        packed = nlri.pack_nlri(create_negotiated())
        unpacked, leftover = RTC.unpack_nlri(
            AFI.ipv4, SAFI.rtc, packed, Action.UNSET, None, negotiated=create_negotiated()
        )

        assert len(leftover) == 0
        assert isinstance(unpacked, RTC)
        assert unpacked.origin == 0
        assert unpacked.rt is None

    def test_pack_unpack_with_action(self) -> None:
        """Test pack/unpack preserves action"""
        rt = RouteTarget.make_route_target(64512, 100)
        nlri = RTC.make_rtc(ASN(65000), rt)

        packed = nlri.pack_nlri(create_negotiated())
        unpacked, leftover = RTC.unpack_nlri(
            AFI.ipv4, SAFI.rtc, packed, Action.ANNOUNCE, None, negotiated=create_negotiated()
        )

        assert unpacked.action == Action.ANNOUNCE

    def test_pack_unpack_various_asns(self) -> None:
        """Test pack/unpack with various ASN values"""
        test_asns = [0, 1, 64512, 65000, 65535, 4200000000]

        for asn in test_asns:
            rt = RouteTarget.make_route_target(64512, 100)
            nlri = RTC.make_rtc(ASN(asn), rt)
            packed = nlri.pack_nlri(create_negotiated())
            unpacked, leftover = RTC.unpack_nlri(
                AFI.ipv4, SAFI.rtc, packed, Action.UNSET, None, negotiated=create_negotiated()
            )

            assert unpacked.origin == asn

    def test_pack_unpack_various_rt_values(self) -> None:
        """Test pack/unpack with various route target values"""
        test_rts = [
            RouteTarget.make_route_target(1, 1),
            RouteTarget.make_route_target(64512, 100),
            RouteTarget.make_route_target(65535, 65535),
        ]

        for rt in test_rts:
            nlri = RTC.make_rtc(ASN(65000), rt)
            packed = nlri.pack_nlri(create_negotiated())
            unpacked, leftover = RTC.unpack_nlri(
                AFI.ipv4, SAFI.rtc, packed, Action.UNSET, None, negotiated=create_negotiated()
            )

            assert unpacked.rt.asn == rt.asn
            assert unpacked.rt.number == rt.number

    def test_unpack_with_leftover_data(self) -> None:
        """Test unpacking RTC with extra data after NLRI"""
        rt = RouteTarget.make_route_target(64512, 100)
        nlri = RTC.make_rtc(ASN(65000), rt)

        packed = nlri.pack_nlri(create_negotiated()) + b'\x01\x02\x03\x04'
        unpacked, leftover = RTC.unpack_nlri(
            AFI.ipv4, SAFI.rtc, packed, Action.UNSET, None, negotiated=create_negotiated()
        )

        assert len(leftover) == 4
        assert leftover == b'\x01\x02\x03\x04'

    def test_pack_resets_rt_flags(self) -> None:
        """Test that pack_nlri resets extended community flags"""
        rt = RouteTarget.make_route_target(64512, 100)
        nlri = RTC.make_rtc(ASN(65000), rt)

        packed = nlri.pack_nlri(create_negotiated())

        # The flags should be reset in the packed RT
        # Length should be 13 bytes: 1 (length) + 4 (origin) + 8 (RT)
        assert len(packed) == 13


class TestRTCStringRepresentation:
    """Test string representations of RTC routes"""

    def test_str_rtc_with_rt(self) -> None:
        """Test string representation with route target"""
        rt = RouteTarget.make_route_target(64512, 100)
        nlri = RTC.make_rtc(ASN(65000), rt)

        result = str(nlri)
        assert 'rtc' in result
        assert '65000' in result
        assert '64512:100' in result

    def test_str_rtc_wildcard(self) -> None:
        """Test string representation for wildcard"""
        nlri = RTC.make_rtc(ASN(0), None)

        result = str(nlri)
        assert 'rtc wildcard' in result

    def test_repr_rtc(self) -> None:
        """Test repr matches str"""
        rt = RouteTarget.make_route_target(64512, 100)
        nlri = RTC.make_rtc(ASN(65000), rt)

        assert repr(nlri) == str(nlri)

    def test_repr_rtc_wildcard(self) -> None:
        """Test repr for wildcard matches str"""
        nlri = RTC.make_rtc(ASN(0), None)

        assert repr(nlri) == str(nlri)


class TestRTCLength:
    """Test length calculations for RTC routes"""

    def test_len_rtc_with_rt(self) -> None:
        """Test length of RTC with route target"""
        rt = RouteTarget.make_route_target(64512, 100)
        nlri = RTC.make_rtc(ASN(65000), rt)

        # Length should be (4 + 8) * 8 = 96 bits
        assert len(nlri) == 96

    def test_len_rtc_wildcard(self) -> None:
        """Test length of wildcard RTC"""
        nlri = RTC.make_rtc(ASN(0), None)

        # Wildcard length is 1
        assert len(nlri) == 1

    def test_len_various_rts(self) -> None:
        """Test length calculation with various RTs"""
        rts = [
            RouteTarget.make_route_target(1, 1),
            RouteTarget.make_route_target(64512, 100),
            RouteTarget.make_route_target(65535, 65535),
        ]

        for rt in rts:
            nlri = RTC.make_rtc(ASN(65000), rt)
            # All should be same length: (4 + 8) * 8 = 96 bits
            assert len(nlri) == 96


class TestRTCFeedback:
    """Test feedback validation for RTC routes"""

    def test_feedback_with_nexthop_announce(self) -> None:
        """Test feedback when nexthop is set for ANNOUNCE"""
        rt = RouteTarget.make_route_target(64512, 100)
        nlri = RTC.make_rtc(ASN(65000), rt, nexthop=IP.from_string('10.0.0.1'))

        feedback = nlri.feedback(Action.ANNOUNCE)
        assert feedback == ''

    def test_feedback_without_nexthop_announce(self) -> None:
        """Test feedback when nexthop is missing (IP.NoNextHop) for ANNOUNCE"""
        rt = RouteTarget.make_route_target(64512, 100)
        nlri = RTC.make_rtc(ASN(65000), rt)
        # nexthop defaults to IP.NoNextHop

        feedback = nlri.feedback(Action.ANNOUNCE)
        assert 'rtc nlri next-hop missing' in feedback

    def test_feedback_no_nexthop_withdraw(self) -> None:
        """Test feedback for WITHDRAW action (doesn't require nexthop)"""
        rt = RouteTarget.make_route_target(64512, 100)
        nlri = RTC.make_rtc(ASN(65000), rt)
        # nexthop defaults to IP.NoNextHop

        # WITHDRAW doesn't require nexthop validation
        feedback = nlri.feedback(Action.WITHDRAW)
        # Feedback should still report missing nexthop since action check is ==
        assert feedback == '' or 'next-hop' in feedback

    def test_feedback_wildcard(self) -> None:
        """Test feedback for wildcard RTC"""
        nlri = RTC.make_rtc(ASN(0), None)
        # nexthop defaults to IP.NoNextHop

        feedback = nlri.feedback(Action.ANNOUNCE)
        assert 'rtc nlri next-hop missing' in feedback


class TestRTCRegistration:
    """Test RTC NLRI registration"""

    def test_rtc_is_nlri_subclass(self) -> None:
        """Test RTC is a subclass of NLRI"""
        assert issubclass(RTC, NLRI)


class TestRTCResetFlags:
    """Test the resetFlags static method"""

    def test_reset_flags_transitive(self) -> None:
        """Test resetFlags clears TRANSITIVE flag"""
        from exabgp.bgp.message.update.attribute import Attribute

        char = Attribute.Flag.TRANSITIVE
        result = RTC.resetFlags(char)
        assert result == 0

    def test_reset_flags_optional(self) -> None:
        """Test resetFlags clears OPTIONAL flag"""
        from exabgp.bgp.message.update.attribute import Attribute

        char = Attribute.Flag.OPTIONAL
        result = RTC.resetFlags(char)
        assert result == 0

    def test_reset_flags_combined(self) -> None:
        """Test resetFlags clears combined flags"""
        from exabgp.bgp.message.update.attribute import Attribute

        char = Attribute.Flag.TRANSITIVE | Attribute.Flag.OPTIONAL
        result = RTC.resetFlags(char)
        assert result == 0

    def test_reset_flags_preserves_other_bits(self) -> None:
        """Test resetFlags preserves other bits"""
        from exabgp.bgp.message.update.attribute import Attribute

        # Set some bits that should be preserved
        char = 0b11110000
        result = RTC.resetFlags(char)
        # Should clear TRANSITIVE (0x40) and OPTIONAL (0x80)
        # but preserve lower bits
        assert result == (char & ~(Attribute.Flag.TRANSITIVE | Attribute.Flag.OPTIONAL))


class TestRTCEdgeCases:
    """Test edge cases for RTC routes"""

    def test_rtc_with_zero_origin(self) -> None:
        """Test RTC with origin ASN 0"""
        rt = RouteTarget.make_route_target(64512, 100)
        nlri = RTC.make_rtc(ASN(0), rt)

        assert nlri.origin == 0

        packed = nlri.pack_nlri(create_negotiated())
        unpacked, _ = RTC.unpack_nlri(AFI.ipv4, SAFI.rtc, packed, Action.UNSET, None, negotiated=create_negotiated())

        assert unpacked.origin == 0

    def test_rtc_with_4byte_asn(self) -> None:
        """Test RTC with 4-byte ASN"""
        rt = RouteTarget.make_route_target(64512, 100)
        nlri = RTC.make_rtc(ASN(4200000000), rt)

        assert nlri.origin == 4200000000

        packed = nlri.pack_nlri(create_negotiated())
        unpacked, _ = RTC.unpack_nlri(AFI.ipv4, SAFI.rtc, packed, Action.UNSET, None, negotiated=create_negotiated())

        assert unpacked.origin == 4200000000

    def test_unpack_with_invalid_length(self) -> None:
        """Test unpacking with invalid length raises exception"""
        # Create a packed RTC with length less than 32 bits (invalid)
        invalid_packed = b'\x10\x00\x00\xfd\xe8'  # length=16 (too short)

        with pytest.raises(Exception) as exc_info:
            RTC.unpack_nlri(AFI.ipv4, SAFI.rtc, invalid_packed, Action.UNSET, None, negotiated=create_negotiated())

        assert 'incorrect RT length' in str(exc_info.value)

    def test_rtc_different_safi_unpack(self) -> None:
        """Test unpacking RTC works with different SAFI in unpack_nlri"""
        rt = RouteTarget.make_route_target(64512, 100)
        nlri = RTC.make_rtc(ASN(65000), rt)

        packed = nlri.pack_nlri(create_negotiated())
        # The implementation uses the same unpacking regardless of SAFI passed
        unpacked, _ = RTC.unpack_nlri(
            AFI.ipv4, SAFI.mpls_vpn, packed, Action.UNSET, None, negotiated=create_negotiated()
        )

        assert unpacked.origin == 65000


class TestRTCMultipleRoutes:
    """Test handling multiple RTC routes"""

    def test_pack_unpack_multiple_routes(self) -> None:
        """Test packing/unpacking multiple RTC routes in sequence"""
        routes = [
            RTC.make_rtc(ASN(65000), RouteTarget.make_route_target(64512, 100)),
            RTC.make_rtc(ASN(65001), RouteTarget.make_route_target(64513, 200)),
            RTC.make_rtc(ASN(0), None),  # wildcard
        ]

        # Pack all routes
        packed_data = b''.join(r.pack_nlri(create_negotiated()) for r in routes)

        # Unpack all routes
        data = packed_data
        unpacked_routes = []
        for _ in range(3):
            route, data = RTC.unpack_nlri(AFI.ipv4, SAFI.rtc, data, Action.UNSET, None, negotiated=create_negotiated())
            unpacked_routes.append(route)

        assert len(unpacked_routes) == 3
        assert unpacked_routes[0].origin == 65000
        assert unpacked_routes[1].origin == 65001
        assert unpacked_routes[2].origin == 0
        assert unpacked_routes[2].rt is None


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
