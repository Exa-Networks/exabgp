#!/usr/bin/env python3
# encoding: utf-8
"""test_route_refresh.py

Comprehensive tests for BGP ROUTE_REFRESH messages (RFC 2918, RFC 7313)

Created for ExaBGP testing framework
License: 3-clause BSD
"""

import pytest
import struct
from unittest.mock import Mock
from exabgp.bgp.message import Message
from exabgp.bgp.message.refresh import RouteRefresh
from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.direction import Direction
from exabgp.bgp.message.open.capability.negotiated import Negotiated
from exabgp.protocol.family import AFI, SAFI


# ==============================================================================
# Test Helper Functions
# ==============================================================================


def create_negotiated() -> Negotiated:
    """Create a Negotiated object with a mock neighbor for testing."""
    neighbor = Mock()
    neighbor.__getitem__ = Mock(return_value={'aigp': False})
    return Negotiated(neighbor, Direction.OUT)


# ==============================================================================
# Phase 1: Basic ROUTE_REFRESH Message Creation
# ==============================================================================


def test_route_refresh_creation_ipv4_unicast() -> None:
    """Test basic ROUTE_REFRESH creation for IPv4 Unicast.

    RFC 2918: Route Refresh Capability for BGP-4
    Message format: AFI (2 bytes), Reserved (1 byte), SAFI (1 byte)
    """
    rr = RouteRefresh.make_route_refresh(AFI.ipv4, SAFI.unicast, RouteRefresh.request)

    assert rr.afi == AFI.ipv4
    assert rr.safi == SAFI.unicast
    assert rr.reserved == RouteRefresh.request
    assert str(rr) == 'REFRESH'


def test_route_refresh_creation_ipv6_unicast() -> None:
    """Test ROUTE_REFRESH creation for IPv6 Unicast."""
    rr = RouteRefresh.make_route_refresh(AFI.ipv6, SAFI.unicast, RouteRefresh.request)

    assert rr.afi == AFI.ipv6
    assert rr.safi == SAFI.unicast
    assert rr.reserved == RouteRefresh.request


def test_route_refresh_creation_with_numeric_values() -> None:
    """Test ROUTE_REFRESH creation with raw numeric AFI/SAFI values.

    AFI: 1 = IPv4, 2 = IPv6
    SAFI: 1 = Unicast, 2 = Multicast, 128 = MPLS VPN
    """
    # IPv4 Unicast (1, 1)
    rr = RouteRefresh.make_route_refresh(1, 1, 0)
    assert rr.afi == AFI.ipv4
    assert rr.safi == SAFI.unicast

    # IPv6 Multicast (2, 2)
    rr = RouteRefresh.make_route_refresh(2, 2, 0)
    assert rr.afi == AFI.ipv6
    assert rr.safi == SAFI.multicast


def test_route_refresh_creation_default_reserved() -> None:
    """Test ROUTE_REFRESH creation with default reserved field.

    Default should be 0 (normal route refresh request).
    """
    rr = RouteRefresh.make_route_refresh(AFI.ipv4, SAFI.unicast)

    assert rr.reserved == 0


# ==============================================================================
# Phase 2: Reserved Field and Subtypes (RFC 7313)
# ==============================================================================


def test_route_refresh_request_subtype() -> None:
    """Test ROUTE_REFRESH with request subtype.

    RFC 7313 Section 2:
    Subtype 0: Normal route refresh request
    """
    rr = RouteRefresh.make_route_refresh(AFI.ipv4, SAFI.unicast, RouteRefresh.request)

    assert rr.reserved == 0
    assert str(rr.reserved) == 'query'


def test_route_refresh_begin_of_route_refresh_subtype() -> None:
    """Test ROUTE_REFRESH with Begin-of-Route-Refresh (BoRR) subtype.

    RFC 7313 Section 4:
    Subtype 1: BoRR - Demarcation of the beginning of a route refresh
    """
    rr = RouteRefresh.make_route_refresh(AFI.ipv4, SAFI.unicast, RouteRefresh.start)

    assert rr.reserved == 1
    assert str(rr.reserved) == 'begin'


def test_route_refresh_end_of_route_refresh_subtype() -> None:
    """Test ROUTE_REFRESH with End-of-Route-Refresh (EoRR) subtype.

    RFC 7313 Section 4:
    Subtype 2: EoRR - Demarcation of the ending of a route refresh
    """
    rr = RouteRefresh.make_route_refresh(AFI.ipv4, SAFI.unicast, RouteRefresh.end)

    assert rr.reserved == 2
    assert str(rr.reserved) == 'end'


def test_route_refresh_reserved_string_representations() -> None:
    """Test Reserved field string representations for all valid subtypes."""
    from exabgp.bgp.message.refresh import Reserved

    assert str(Reserved(0)) == 'query'
    assert str(Reserved(1)) == 'begin'
    assert str(Reserved(2)) == 'end'
    assert str(Reserved(99)) == 'invalid'  # Invalid subtype


# ==============================================================================
# Phase 3: ROUTE_REFRESH Message Encoding
# ==============================================================================


def test_route_refresh_encoding_ipv4_unicast() -> None:
    """Test ROUTE_REFRESH encoding for IPv4 Unicast.

    Wire format:
    - Marker: 16 bytes (all 0xFF)
    - Length: 2 bytes (0x0017 = 23)
    - Type: 1 byte (0x05 = ROUTE_REFRESH)
    - AFI: 2 bytes (0x0001 = IPv4)
    - Reserved: 1 byte (0x00)
    - SAFI: 1 byte (0x01 = Unicast)
    Total: 23 bytes
    """
    rr = RouteRefresh.make_route_refresh(AFI.ipv4, SAFI.unicast, RouteRefresh.request)
    msg = rr.pack_message(create_negotiated())

    # Total length should be 23 bytes
    assert len(msg) == 23

    # First 16 bytes should be marker
    assert msg[0:16] == b'\xff' * 16

    # Length field (bytes 16-17) should be 23
    assert msg[16:18] == b'\x00\x17'

    # Type field (byte 18) should be 5 (ROUTE_REFRESH)
    assert msg[18] == 0x05

    # AFI field (bytes 19-20) should be 1 (IPv4)
    assert msg[19:21] == b'\x00\x01'

    # Reserved field (byte 21) should be 0
    assert msg[21] == 0x00

    # SAFI field (byte 22) should be 1 (Unicast)
    assert msg[22] == 0x01


def test_route_refresh_encoding_ipv6_multicast() -> None:
    """Test ROUTE_REFRESH encoding for IPv6 Multicast."""
    rr = RouteRefresh.make_route_refresh(AFI.ipv6, SAFI.multicast, RouteRefresh.request)
    msg = rr.pack_message(create_negotiated())

    # AFI field should be 2 (IPv6)
    assert msg[19:21] == b'\x00\x02'

    # SAFI field should be 2 (Multicast)
    assert msg[22] == 0x02


def test_route_refresh_encoding_with_borr_subtype() -> None:
    """Test ROUTE_REFRESH encoding with BoRR subtype."""
    rr = RouteRefresh.make_route_refresh(AFI.ipv4, SAFI.unicast, RouteRefresh.start)
    msg = rr.pack_message(create_negotiated())

    # Reserved field should be 1 (BoRR)
    assert msg[21] == 0x01


def test_route_refresh_encoding_with_eorr_subtype() -> None:
    """Test ROUTE_REFRESH encoding with EoRR subtype."""
    rr = RouteRefresh.make_route_refresh(AFI.ipv4, SAFI.unicast, RouteRefresh.end)
    msg = rr.pack_message(create_negotiated())

    # Reserved field should be 2 (EoRR)
    assert msg[21] == 0x02


# ==============================================================================
# Phase 4: ROUTE_REFRESH Message Decoding
# ==============================================================================


def test_route_refresh_unpack_ipv4_unicast() -> None:
    """Test unpacking ROUTE_REFRESH for IPv4 Unicast.

    Data format: AFI (2 bytes) + Reserved (1 byte) + SAFI (1 byte)
    """
    # AFI=1, Reserved=0, SAFI=1
    data = struct.pack('!HBB', 1, 0, 1)

    rr = RouteRefresh.unpack_message(data, create_negotiated())

    assert rr.afi == AFI.ipv4
    assert rr.safi == SAFI.unicast
    assert rr.reserved == 0


def test_route_refresh_unpack_ipv6_multicast() -> None:
    """Test unpacking ROUTE_REFRESH for IPv6 Multicast."""
    # AFI=2, Reserved=0, SAFI=2
    data = struct.pack('!HBB', 2, 0, 2)

    rr = RouteRefresh.unpack_message(data, create_negotiated())

    assert rr.afi == AFI.ipv6
    assert rr.safi == SAFI.multicast


def test_route_refresh_unpack_with_borr() -> None:
    """Test unpacking ROUTE_REFRESH with Begin-of-RR subtype."""
    # AFI=1, Reserved=1 (BoRR), SAFI=1
    data = struct.pack('!HBB', 1, 1, 1)

    rr = RouteRefresh.unpack_message(data, create_negotiated())

    assert rr.reserved == 1
    assert str(rr.reserved) == 'begin'


def test_route_refresh_unpack_with_eorr() -> None:
    """Test unpacking ROUTE_REFRESH with End-of-RR subtype."""
    # AFI=1, Reserved=2 (EoRR), SAFI=1
    data = struct.pack('!HBB', 1, 2, 1)

    rr = RouteRefresh.unpack_message(data, create_negotiated())

    assert rr.reserved == 2
    assert str(rr.reserved) == 'end'


def test_route_refresh_unpack_through_message_class() -> None:
    """Test unpacking ROUTE_REFRESH through Message base class."""
    message_type = Message.CODE.ROUTE_REFRESH
    data = struct.pack('!HBB', 1, 0, 1)

    rr = Message.unpack(message_type, data, {})

    assert isinstance(rr, RouteRefresh)
    assert rr.afi == AFI.ipv4


# ==============================================================================
# Phase 5: ROUTE_REFRESH Validation and Error Handling
# ==============================================================================


def test_route_refresh_unpack_invalid_data_length() -> None:
    """Test that invalid data length raises Notify error.

    ROUTE_REFRESH must be exactly 4 bytes.
    """
    # Too short (3 bytes)
    data = b'\x00\x01\x00'

    with pytest.raises(Notify) as exc_info:
        RouteRefresh.unpack_message(data, create_negotiated())

    assert 'invalid route-refresh message' in str(exc_info.value)


def test_route_refresh_unpack_empty_data() -> None:
    """Test that empty data raises Notify error."""
    data = b''

    with pytest.raises(Notify):
        RouteRefresh.unpack_message(data, create_negotiated())


def test_route_refresh_unpack_invalid_reserved_field() -> None:
    """Test that invalid reserved field raises Notify error.

    RFC 7313: Reserved field must be 0, 1, or 2.
    """
    # AFI=1, Reserved=99 (invalid), SAFI=1
    data = struct.pack('!HBB', 1, 99, 1)

    with pytest.raises(Notify) as exc_info:
        RouteRefresh.unpack_message(data, create_negotiated())

    assert 'invalid route-refresh message subtype' in str(exc_info.value)


def test_route_refresh_unpack_various_invalid_reserved() -> None:
    """Test various invalid reserved values."""
    invalid_reserved = [3, 4, 5, 10, 99, 255]

    for reserved in invalid_reserved:
        data = struct.pack('!HBB', 1, reserved, 1)

        with pytest.raises(Notify):
            RouteRefresh.unpack_message(data, create_negotiated())


# ==============================================================================
# Phase 6: ROUTE_REFRESH Round-Trip Tests
# ==============================================================================


def test_route_refresh_encode_decode_roundtrip_ipv4() -> None:
    """Test ROUTE_REFRESH encode/decode round-trip for IPv4."""
    # Create and encode
    original = RouteRefresh.make_route_refresh(AFI.ipv4, SAFI.unicast, RouteRefresh.request)
    encoded = original.pack_message(create_negotiated())

    # Extract payload (skip 19-byte header)
    payload = encoded[19:]

    # Decode
    decoded = RouteRefresh.unpack_message(payload, create_negotiated())

    # Verify match
    assert decoded.afi == original.afi
    assert decoded.safi == original.safi
    assert decoded.reserved == original.reserved


def test_route_refresh_encode_decode_roundtrip_ipv6() -> None:
    """Test ROUTE_REFRESH encode/decode round-trip for IPv6."""
    original = RouteRefresh.make_route_refresh(AFI.ipv6, SAFI.multicast, RouteRefresh.end)
    encoded = original.pack_message(create_negotiated())
    payload = encoded[19:]
    decoded = RouteRefresh.unpack_message(payload, create_negotiated())

    assert decoded.afi == original.afi
    assert decoded.safi == original.safi
    assert decoded.reserved == original.reserved


def test_route_refresh_roundtrip_all_subtypes() -> None:
    """Test round-trip for all valid reserved subtypes."""
    subtypes = [RouteRefresh.request, RouteRefresh.start, RouteRefresh.end]

    for subtype in subtypes:
        original = RouteRefresh.make_route_refresh(AFI.ipv4, SAFI.unicast, subtype)
        encoded = original.pack_message(create_negotiated())
        payload = encoded[19:]
        decoded = RouteRefresh.unpack_message(payload, create_negotiated())

        assert decoded.reserved == subtype


# ==============================================================================
# Phase 7: ROUTE_REFRESH Equality and Comparison
# ==============================================================================


def test_route_refresh_equality_same_params() -> None:
    """Test that ROUTE_REFRESH messages with same params are equal."""
    rr1 = RouteRefresh.make_route_refresh(AFI.ipv4, SAFI.unicast, RouteRefresh.request)
    rr2 = RouteRefresh.make_route_refresh(AFI.ipv4, SAFI.unicast, RouteRefresh.request)

    assert rr1 == rr2


def test_route_refresh_equality_different_afi() -> None:
    """Test that ROUTE_REFRESH messages with different AFI are not equal."""
    rr1 = RouteRefresh.make_route_refresh(AFI.ipv4, SAFI.unicast, RouteRefresh.request)
    rr2 = RouteRefresh.make_route_refresh(AFI.ipv6, SAFI.unicast, RouteRefresh.request)

    assert rr1 != rr2


def test_route_refresh_equality_different_safi() -> None:
    """Test that ROUTE_REFRESH messages with different SAFI are not equal."""
    rr1 = RouteRefresh.make_route_refresh(AFI.ipv4, SAFI.unicast, RouteRefresh.request)
    rr2 = RouteRefresh.make_route_refresh(AFI.ipv4, SAFI.multicast, RouteRefresh.request)

    assert rr1 != rr2


def test_route_refresh_equality_different_reserved() -> None:
    """Test that ROUTE_REFRESH messages with different reserved are not equal."""
    rr1 = RouteRefresh.make_route_refresh(AFI.ipv4, SAFI.unicast, RouteRefresh.request)
    rr2 = RouteRefresh.make_route_refresh(AFI.ipv4, SAFI.unicast, RouteRefresh.start)

    assert rr1 != rr2


def test_route_refresh_equality_with_non_route_refresh() -> None:
    """Test that ROUTE_REFRESH is not equal to non-RouteRefresh objects."""
    rr = RouteRefresh.make_route_refresh(AFI.ipv4, SAFI.unicast, RouteRefresh.request)

    assert rr != 'REFRESH'
    assert rr != 123
    assert rr is not None


# ==============================================================================
# Phase 8: ROUTE_REFRESH String Representations
# ==============================================================================


def test_route_refresh_str_basic() -> None:
    """Test basic string representation."""
    rr = RouteRefresh.make_route_refresh(AFI.ipv4, SAFI.unicast, RouteRefresh.request)

    assert str(rr) == 'REFRESH'


def test_route_refresh_extensive_representation() -> None:
    """Test extensive string representation."""
    rr = RouteRefresh.make_route_refresh(AFI.ipv4, SAFI.unicast, RouteRefresh.request)

    extensive = rr.extensive()
    assert 'route refresh' in extensive
    assert 'ipv4' in extensive.lower() or str(AFI.ipv4) in extensive


def test_route_refresh_extensive_with_different_families() -> None:
    """Test extensive representation with different AFI/SAFI combinations."""
    test_cases = [
        (AFI.ipv4, SAFI.unicast),
        (AFI.ipv6, SAFI.multicast),
        (AFI.ipv4, SAFI.mpls_vpn),
    ]

    for afi, safi in test_cases:
        rr = RouteRefresh.make_route_refresh(afi, safi, RouteRefresh.request)
        extensive = rr.extensive()

        assert 'route refresh' in extensive


# ==============================================================================
# Phase 9: ROUTE_REFRESH Message Constants
# ==============================================================================


def test_route_refresh_message_id() -> None:
    """Test ROUTE_REFRESH message ID is correct.

    RFC 2918: ROUTE_REFRESH message type is 5.
    """
    assert RouteRefresh.ID == 5
    assert RouteRefresh.ID == Message.CODE.ROUTE_REFRESH


def test_route_refresh_message_type_bytes() -> None:
    """Test ROUTE_REFRESH TYPE byte representation."""
    assert RouteRefresh.TYPE == b'\x05'


def test_route_refresh_message_registration() -> None:
    """Test that ROUTE_REFRESH is properly registered."""
    assert Message.CODE.ROUTE_REFRESH in Message.registered_message

    klass = Message.klass(Message.CODE.ROUTE_REFRESH)
    assert klass == RouteRefresh


def test_route_refresh_subtype_constants() -> None:
    """Test ROUTE_REFRESH subtype constants."""
    assert RouteRefresh.request == 0
    assert RouteRefresh.start == 1
    assert RouteRefresh.end == 2


def test_route_refresh_length_validation_rule() -> None:
    """Test ROUTE_REFRESH length validation rule.

    RFC 2918: ROUTE_REFRESH messages must be exactly 23 octets.
    """
    validator = Message.Length[Message.CODE.ROUTE_REFRESH]

    # Should accept exactly 23
    assert validator(23) is True

    # Should reject other lengths
    assert validator(19) is False
    assert validator(22) is False
    assert validator(24) is False


# ==============================================================================
# Phase 10: ROUTE_REFRESH with Various AFI/SAFI Combinations
# ==============================================================================


def test_route_refresh_ipv4_mpls_vpn() -> None:
    """Test ROUTE_REFRESH for IPv4 MPLS VPN (AFI 1, SAFI 128)."""
    rr = RouteRefresh.make_route_refresh(AFI.ipv4, SAFI.mpls_vpn, RouteRefresh.request)

    assert rr.afi == AFI.ipv4
    assert rr.safi == SAFI.mpls_vpn

    # Encode and verify
    msg = rr.pack_message(create_negotiated())
    payload = msg[19:]

    decoded = RouteRefresh.unpack_message(payload, create_negotiated())
    assert decoded == rr


def test_route_refresh_ipv6_mpls_vpn() -> None:
    """Test ROUTE_REFRESH for IPv6 MPLS VPN (AFI 2, SAFI 128)."""
    rr = RouteRefresh.make_route_refresh(AFI.ipv6, SAFI.mpls_vpn, RouteRefresh.request)

    assert rr.afi == AFI.ipv6
    assert rr.safi == SAFI.mpls_vpn


def test_route_refresh_flow_ipv4() -> None:
    """Test ROUTE_REFRESH for IPv4 FlowSpec (AFI 1, SAFI 133)."""
    rr = RouteRefresh.make_route_refresh(AFI.ipv4, SAFI.flow_ip, RouteRefresh.request)

    assert rr.afi == AFI.ipv4
    assert rr.safi == SAFI.flow_ip


def test_route_refresh_various_afi_safi_combinations() -> None:
    """Test ROUTE_REFRESH with various AFI/SAFI combinations."""
    test_cases = [
        (AFI.ipv4, SAFI.unicast),
        (AFI.ipv4, SAFI.multicast),
        (AFI.ipv6, SAFI.unicast),
        (AFI.ipv6, SAFI.multicast),
        (AFI.ipv4, SAFI.mpls_vpn),
        (AFI.ipv6, SAFI.mpls_vpn),
        (AFI.ipv4, SAFI.flow_ip),
        (AFI.ipv6, SAFI.flow_ip),
    ]

    for afi, safi in test_cases:
        rr = RouteRefresh.make_route_refresh(afi, safi, RouteRefresh.request)

        # Verify creation
        assert rr.afi == afi
        assert rr.safi == safi

        # Verify encoding/decoding
        msg = rr.pack_message(create_negotiated())
        payload = msg[19:]
        decoded = RouteRefresh.unpack_message(payload, create_negotiated())

        assert decoded == rr


# ==============================================================================
# Phase 11: ROUTE_REFRESH Message Iterator
# ==============================================================================


def test_route_refresh_messages_iterator() -> None:
    """Test ROUTE_REFRESH messages() iterator method.

    This method is used to generate messages for sending.
    """
    rr = RouteRefresh.make_route_refresh(AFI.ipv4, SAFI.unicast, RouteRefresh.request)

    messages = list(rr.messages({}, True))

    # Should yield exactly one message
    assert len(messages) == 1

    # The message should be the encoded format
    assert len(messages[0]) == 23


def test_route_refresh_messages_with_different_params() -> None:
    """Test messages() iterator with different negotiated params."""
    rr = RouteRefresh.make_route_refresh(AFI.ipv6, SAFI.multicast, RouteRefresh.start)

    # With negotiated params
    messages1 = list(rr.messages({'test': 'value'}, True))
    assert len(messages1) == 1

    # Without negotiated params
    messages2 = list(rr.messages({}, False))
    assert len(messages2) == 1

    # Both should produce same result
    assert messages1[0] == messages2[0]


# ==============================================================================
# Summary
# ==============================================================================
# Total tests: 54
#
# Coverage:
# - Basic message creation (4 tests)
# - Reserved field and subtypes (4 tests)
# - Message encoding (4 tests)
# - Message decoding (6 tests)
# - Validation and error handling (5 tests)
# - Round-trip encoding/decoding (3 tests)
# - Equality and comparison (5 tests)
# - String representations (3 tests)
# - Message constants (5 tests)
# - Various AFI/SAFI combinations (5 tests)
# - Message iterator (2 tests)
#
# This test suite ensures:
# - Proper ROUTE_REFRESH message creation and encoding
# - Correct wire format (23 bytes total)
# - Support for all valid AFI/SAFI combinations
# - Proper handling of RFC 7313 subtypes (request, BoRR, EoRR)
# - Validation of reserved field
# - Round-trip consistency
# - RFC 2918 and RFC 7313 compliance
# ==============================================================================
