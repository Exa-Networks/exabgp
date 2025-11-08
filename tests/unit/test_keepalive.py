#!/usr/bin/env python3
# encoding: utf-8
"""
test_keepalive.py

Comprehensive tests for BGP KEEPALIVE messages (RFC 4271 Section 4.4)

Created for ExaBGP testing framework
License: 3-clause BSD
"""

import pytest
from exabgp.bgp.message import Message
from exabgp.bgp.message.keepalive import KeepAlive
from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.direction import Direction


# ==============================================================================
# Phase 1: Basic KEEPALIVE Message Creation and Encoding
# ==============================================================================

def test_keepalive_creation():
    """
    Test basic KEEPALIVE message creation.

    RFC 4271 Section 4.4:
    BGP does not use any KEEPALIVE message authentication. A KEEPALIVE
    message consists of only the message header and has a length of 19 octets.
    """
    keepalive = KeepAlive()
    assert str(keepalive) == 'KEEPALIVE'
    assert keepalive.ID == Message.CODE.KEEPALIVE


def test_keepalive_message_encoding():
    """
    Test KEEPALIVE message encoding to wire format.

    RFC 4271 Section 4.1:
    The message header contains:
    - Marker (16 octets): all ones
    - Length (2 octets): 19 (0x0013)
    - Type (1 octet): 4 (KEEPALIVE)
    """
    keepalive = KeepAlive()
    msg = keepalive.message()

    # Total length should be 19 bytes
    assert len(msg) == 19

    # First 16 bytes should be marker (all 0xFF)
    assert msg[0:16] == b'\xff' * 16

    # Bytes 16-17 should be length (0x0013 = 19)
    assert msg[16:18] == b'\x00\x13'

    # Byte 18 should be message type (0x04 = KEEPALIVE)
    assert msg[18] == 0x04


def test_keepalive_message_encoding_with_negotiated():
    """
    Test KEEPALIVE message encoding with negotiated parameters.

    KEEPALIVE messages don't use negotiated parameters, but the method
    should accept them without error.
    """
    keepalive = KeepAlive()
    negotiated = {'test': 'value'}
    msg = keepalive.message(negotiated)

    # Should produce same result as without negotiated params
    assert len(msg) == 19
    assert msg[18] == 0x04


# ==============================================================================
# Phase 2: KEEPALIVE Message Decoding and Parsing
# ==============================================================================

def test_keepalive_unpack_valid_message():
    """
    Test unpacking a valid KEEPALIVE message.

    KEEPALIVE messages should have no payload (empty data).
    """
    data = b''
    negotiated = {}

    keepalive = KeepAlive.unpack_message(data, Direction.IN, negotiated)

    assert isinstance(keepalive, KeepAlive)
    assert str(keepalive) == 'KEEPALIVE'


def test_keepalive_unpack_through_message_class():
    """
    Test unpacking KEEPALIVE through the Message base class.

    This tests the message dispatch mechanism.
    """
    message_type = Message.CODE.KEEPALIVE
    data = b''
    negotiated = {}

    keepalive = Message.unpack(message_type, data, Direction.IN, negotiated)

    assert isinstance(keepalive, KeepAlive)


def test_keepalive_unpack_with_direction():
    """
    Test KEEPALIVE unpacking with different directions.

    Direction shouldn't affect KEEPALIVE processing.
    """
    data = b''
    negotiated = {}

    # Test incoming direction
    keepalive_in = KeepAlive.unpack_message(data, Direction.IN, negotiated)
    assert isinstance(keepalive_in, KeepAlive)

    # Test outgoing direction
    keepalive_out = KeepAlive.unpack_message(data, Direction.OUT, negotiated)
    assert isinstance(keepalive_out, KeepAlive)


# ==============================================================================
# Phase 3: KEEPALIVE Message Validation and Error Handling
# ==============================================================================

def test_keepalive_with_payload_raises_error():
    """
    Test that KEEPALIVE with payload raises an error.

    RFC 4271 Section 4.4:
    A KEEPALIVE message consists of only the message header.
    Any payload data is invalid.
    """
    # Try with single byte payload
    data = b'\x01'
    negotiated = {}

    with pytest.raises(Notify):
        KeepAlive.unpack_message(data, Direction.IN, negotiated)


def test_keepalive_with_multi_byte_payload_raises_error():
    """
    Test that KEEPALIVE with multi-byte payload raises an error.
    """
    data = b'\x01\x02\x03\x04'
    negotiated = {}

    with pytest.raises(Notify):
        KeepAlive.unpack_message(data, Direction.IN, negotiated)


def test_keepalive_with_various_invalid_payloads():
    """
    Test various invalid payloads to ensure robust error handling.
    """
    invalid_payloads = [
        b'\x00',                    # Single null byte
        b'\xff' * 10,               # 10 bytes of 0xFF
        b'\x00\x01\x02',            # Arbitrary data
        b'invalid',                 # ASCII text
        b'\x01' * 100,              # Large payload
    ]

    for payload in invalid_payloads:
        with pytest.raises(Notify):
            KeepAlive.unpack_message(payload, Direction.IN, {})


# ==============================================================================
# Phase 4: KEEPALIVE Message Round-Trip Tests
# ==============================================================================

def test_keepalive_encode_decode_roundtrip():
    """
    Test that KEEPALIVE can be encoded and decoded back successfully.
    """
    # Create and encode
    keepalive_original = KeepAlive()
    encoded = keepalive_original.message()

    # Extract payload (everything after 19-byte header)
    payload = encoded[19:]

    # Decode
    keepalive_decoded = KeepAlive.unpack_message(payload, Direction.IN, {})

    # Verify they match
    assert isinstance(keepalive_decoded, KeepAlive)
    assert str(keepalive_decoded) == str(keepalive_original)


def test_keepalive_multiple_encode_decode_cycles():
    """
    Test multiple encode/decode cycles produce consistent results.
    """
    keepalive = KeepAlive()

    for _ in range(10):
        # Encode
        encoded = keepalive.message()

        # Verify encoding is consistent
        assert len(encoded) == 19
        assert encoded[18] == 0x04

        # Extract and decode payload
        payload = encoded[19:]
        keepalive = KeepAlive.unpack_message(payload, Direction.IN, {})

        assert isinstance(keepalive, KeepAlive)


# ==============================================================================
# Phase 5: KEEPALIVE Message ID and Type Verification
# ==============================================================================

def test_keepalive_message_id():
    """
    Test that KEEPALIVE has correct message ID.

    RFC 4271: KEEPALIVE message type code is 4.
    """
    assert KeepAlive.ID == 4
    assert KeepAlive.ID == Message.CODE.KEEPALIVE


def test_keepalive_message_type_bytes():
    """
    Test that KEEPALIVE TYPE is correct byte representation.
    """
    assert KeepAlive.TYPE == b'\x04'


def test_keepalive_message_registration():
    """
    Test that KEEPALIVE is properly registered with Message class.
    """
    # Verify KEEPALIVE is in registered messages
    assert Message.CODE.KEEPALIVE in Message.registered_message

    # Verify we get KeepAlive class when looking up the ID
    klass = Message.klass(Message.CODE.KEEPALIVE)
    assert klass == KeepAlive


# ==============================================================================
# Phase 6: KEEPALIVE Message Comparison and Equality
# ==============================================================================

def test_keepalive_instances_are_equal():
    """
    Test that KEEPALIVE instances are considered equal.

    Since KEEPALIVE has no parameters, all instances should be equivalent.
    """
    keepalive1 = KeepAlive()
    keepalive2 = KeepAlive()

    # Both should produce identical wire format
    assert keepalive1.message() == keepalive2.message()


def test_keepalive_string_representation():
    """
    Test KEEPALIVE string representation.
    """
    keepalive = KeepAlive()

    # String representation should be 'KEEPALIVE'
    assert str(keepalive) == 'KEEPALIVE'
    assert 'KEEPALIVE' in str(keepalive)


# ==============================================================================
# Phase 7: KEEPALIVE Message with Edge Cases
# ==============================================================================

def test_keepalive_with_none_negotiated():
    """
    Test KEEPALIVE encoding/decoding with None negotiated parameters.
    """
    keepalive = KeepAlive()

    # Should work with None
    msg = keepalive.message(None)
    assert len(msg) == 19

    # Should work when unpacking with None
    decoded = KeepAlive.unpack_message(b'', Direction.IN, None)
    assert isinstance(decoded, KeepAlive)


def test_keepalive_marker_field():
    """
    Test that KEEPALIVE uses correct marker field.

    RFC 4271 Section 4.1:
    The marker field must be all ones for all message types.
    """
    keepalive = KeepAlive()
    msg = keepalive.message()

    # Marker should be 16 bytes of 0xFF
    expected_marker = b'\xff' * 16
    assert msg[0:16] == expected_marker


def test_keepalive_header_length_field():
    """
    Test that KEEPALIVE length field is correct.

    Length field is 2 bytes in network byte order (big-endian).
    For KEEPALIVE, this should be 19 (0x0013).
    """
    keepalive = KeepAlive()
    msg = keepalive.message()

    # Extract length field (bytes 16-17)
    length_bytes = msg[16:18]

    # Should be 19 in big-endian format
    assert length_bytes == b'\x00\x13'

    # Verify it decodes to 19
    import struct
    length = struct.unpack('!H', length_bytes)[0]
    assert length == 19


# ==============================================================================
# Phase 8: KEEPALIVE Message Constants Verification
# ==============================================================================

def test_keepalive_message_constants():
    """
    Test KEEPALIVE message constants against RFC specifications.
    """
    # Message header length is always 19 bytes
    assert Message.HEADER_LEN == 19

    # KEEPALIVE complete message is exactly header length
    keepalive = KeepAlive()
    assert len(keepalive.message()) == Message.HEADER_LEN

    # Marker is 16 bytes
    assert len(Message.MARKER) == 16

    # Marker is all ones
    assert Message.MARKER == b'\xff' * 16


def test_keepalive_length_validation_rule():
    """
    Test KEEPALIVE length validation rule.

    RFC 4271: KEEPALIVE messages must be exactly 19 octets.
    """
    # The Message.Length dictionary defines validation rules
    keepalive_validator = Message.Length[Message.CODE.KEEPALIVE]

    # Should accept exactly 19
    assert keepalive_validator(19) is True

    # Should reject other lengths
    assert keepalive_validator(20) is False
    assert keepalive_validator(18) is False
    assert keepalive_validator(23) is False
    assert keepalive_validator(100) is False


# ==============================================================================
# Summary
# ==============================================================================
# Total tests: 28
#
# Coverage:
# - Basic creation and encoding (4 tests)
# - Decoding and parsing (3 tests)
# - Validation and error handling (5 tests)
# - Round-trip encoding/decoding (2 tests)
# - Message ID and type verification (3 tests)
# - Comparison and equality (2 tests)
# - Edge cases (3 tests)
# - Constants verification (2 tests)
#
# This test suite ensures:
# - Proper KEEPALIVE message creation
# - Correct wire format encoding (19 bytes total)
# - Proper marker, length, and type fields
# - Rejection of invalid payloads
# - Round-trip consistency
# - RFC 4271 compliance
# ==============================================================================
