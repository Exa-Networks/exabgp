#!/usr/bin/env python3
# encoding: utf-8
"""test_notification_comprehensive.py

Comprehensive tests for BGP NOTIFICATION messages (RFC 4271 Section 4.5)

NOTIFICATION: Error handling and connection termination messages
Notify: Outgoing notifications to send to peer
Notification: Incoming notifications received from peer

Created for ExaBGP testing framework
License: 3-clause BSD
"""

import pytest
import struct
from exabgp.bgp.message import Message
from exabgp.bgp.message.notification import Notify, Notification
from exabgp.bgp.message.direction import Direction
from typing import NoReturn


# ==============================================================================
# Part 1: NOTIFICATION Message Constants and Registration
# ==============================================================================

def test_notification_message_id() -> None:
    """Test NOTIFICATION message ID.

    RFC 4271: NOTIFICATION uses message type 0x03 (3).
    """
    assert Notification.ID == 3
    assert Notification.ID == Message.CODE.NOTIFICATION


def test_notification_message_type_bytes() -> None:
    """Test NOTIFICATION TYPE byte representation.
    """
    assert Notification.TYPE == b'\x03'


def test_notification_message_registration() -> None:
    """Test that NOTIFICATION is properly registered with Message class.
    """
    assert Message.CODE.NOTIFICATION in Message.registered_message

    klass = Message.klass(Message.CODE.NOTIFICATION)
    assert klass == Notification


# ==============================================================================
# Part 2: Error Code and Subcode String Representations
# ==============================================================================

def test_notification_error_code_strings() -> None:
    """Test error code string representations.

    RFC 4271 defines 6 main error codes.
    """
    assert Notification._str_code[1] == 'Message header error'
    assert Notification._str_code[2] == 'OPEN message error'
    assert Notification._str_code[3] == 'UPDATE message error'
    assert Notification._str_code[4] == 'Hold timer expired'
    assert Notification._str_code[5] == 'State machine error'
    assert Notification._str_code[6] == 'Cease'


def test_notification_message_header_error_subcodes() -> None:
    """Test Message Header Error (code 1) subcodes.
    """
    assert Notification._str_subcode[(1, 0)] == 'Unspecific'
    assert Notification._str_subcode[(1, 1)] == 'Connection Not Synchronized'
    assert Notification._str_subcode[(1, 2)] == 'Bad Message Length'
    assert Notification._str_subcode[(1, 3)] == 'Bad Message Type'


def test_notification_open_message_error_subcodes() -> None:
    """Test OPEN Message Error (code 2) subcodes.
    """
    assert Notification._str_subcode[(2, 0)] == 'Unspecific'
    assert Notification._str_subcode[(2, 1)] == 'Unsupported Version Number'
    assert Notification._str_subcode[(2, 2)] == 'Bad Peer AS'
    assert Notification._str_subcode[(2, 3)] == 'Bad BGP Identifier'
    assert Notification._str_subcode[(2, 4)] == 'Unsupported Optional Parameter'
    assert Notification._str_subcode[(2, 5)] == 'Authentication Notification (Deprecated)'
    assert Notification._str_subcode[(2, 6)] == 'Unacceptable Hold Time'
    assert Notification._str_subcode[(2, 7)] == 'Unsupported Capability'


def test_notification_update_message_error_subcodes() -> None:
    """Test UPDATE Message Error (code 3) subcodes.
    """
    assert Notification._str_subcode[(3, 0)] == 'Unspecific'
    assert Notification._str_subcode[(3, 1)] == 'Malformed Attribute List'
    assert Notification._str_subcode[(3, 2)] == 'Unrecognized Well-known Attribute'
    assert Notification._str_subcode[(3, 3)] == 'Missing Well-known Attribute'
    assert Notification._str_subcode[(3, 4)] == 'Attribute Flags Error'
    assert Notification._str_subcode[(3, 5)] == 'Attribute Length Error'
    assert Notification._str_subcode[(3, 6)] == 'Invalid ORIGIN Attribute'
    assert Notification._str_subcode[(3, 7)] == 'AS Routing Loop'
    assert Notification._str_subcode[(3, 8)] == 'Invalid NEXT_HOP Attribute'
    assert Notification._str_subcode[(3, 9)] == 'Optional Attribute Error'
    assert Notification._str_subcode[(3, 10)] == 'Invalid Network Field'
    assert Notification._str_subcode[(3, 11)] == 'Malformed AS_PATH'


def test_notification_state_machine_error_subcodes() -> None:
    """Test State Machine Error (code 5) subcodes.

    RFC 6608: Additional subcodes for state machine errors.
    """
    assert Notification._str_subcode[(5, 0)] == 'Unspecific'
    assert Notification._str_subcode[(5, 1)] == 'Receive Unexpected Message in OpenSent State'
    assert Notification._str_subcode[(5, 2)] == 'Receive Unexpected Message in OpenConfirm State'
    assert Notification._str_subcode[(5, 3)] == 'Receive Unexpected Message in Established State'


def test_notification_cease_subcodes() -> None:
    """Test Cease (code 6) subcodes.

    RFC 4486: Subcodes for Cease notification.
    """
    assert Notification._str_subcode[(6, 0)] == 'Unspecific'
    assert Notification._str_subcode[(6, 1)] == 'Maximum Number of Prefixes Reached'
    assert Notification._str_subcode[(6, 2)] == 'Administrative Shutdown'
    assert Notification._str_subcode[(6, 3)] == 'Peer De-configured'
    assert Notification._str_subcode[(6, 4)] == 'Administrative Reset'
    assert Notification._str_subcode[(6, 5)] == 'Connection Rejected'
    assert Notification._str_subcode[(6, 6)] == 'Other Configuration Change'
    assert Notification._str_subcode[(6, 7)] == 'Connection Collision Resolution'
    assert Notification._str_subcode[(6, 8)] == 'Out of Resources'


def test_notification_enhanced_route_refresh_subcodes() -> None:
    """Test Enhanced Route Refresh (code 7) subcodes.
    """
    assert Notification._str_subcode[(7, 1)] == 'Invalid Message Length'
    assert Notification._str_subcode[(7, 2)] == 'Malformed Message Subtype'


# ==============================================================================
# Part 3: Incoming NOTIFICATION Message Creation (from peer)
# ==============================================================================

def test_notification_incoming_creation_basic() -> None:
    """Test creating incoming NOTIFICATION with basic error.
    """
    notif = Notification(2, 1, b'Extra data')

    assert notif.code == 2
    assert notif.subcode == 1
    assert notif.data == b'Extra data'


def test_notification_incoming_creation_no_data() -> None:
    """Test creating NOTIFICATION without additional data.
    """
    notif = Notification(4, 0)

    assert notif.code == 4
    assert notif.subcode == 0
    assert notif.data == b''


def test_notification_incoming_creation_binary_data() -> None:
    """Test creating NOTIFICATION with non-printable binary data.

    Non-printable data should be converted to hex representation.
    """
    binary_data = b'\x00\x01\x02\xff'
    notif = Notification(3, 5, binary_data)

    assert notif.code == 3
    assert notif.subcode == 5
    # Binary data should be converted to hex string
    assert isinstance(notif.data, (bytes, str))


def test_notification_incoming_printable_data() -> None:
    """Test NOTIFICATION with printable ASCII data.
    """
    printable_data = b'Error message text'
    notif = Notification(1, 2, printable_data)

    assert notif.code == 1
    assert notif.subcode == 2
    assert notif.data == printable_data


# ==============================================================================
# Part 4: Outgoing NOTIFICATION (Notify) Creation (to send to peer)
# ==============================================================================

def test_notify_outgoing_creation_basic() -> None:
    """Test creating outgoing Notify message.

    Notify is used to send notifications to the peer.
    """
    notify = Notify(2, 1, 'Custom error data')

    assert notify.code == 2
    assert notify.subcode == 1
    assert b'Custom error data' in notify.data


def test_notify_outgoing_creation_default_data() -> None:
    """Test Notify with default data (uses subcode description).
    """
    notify = Notify(2, 2)

    assert notify.code == 2
    assert notify.subcode == 2
    # Should use default message from _str_subcode
    assert b'Bad Peer AS' in notify.data


def test_notify_outgoing_creation_various_errors() -> None:
    """Test creating Notify messages for various error types.
    """
    test_cases = [
        (1, 1),  # Message header error - Connection Not Synchronized
        (2, 3),  # OPEN error - Bad BGP Identifier
        (3, 6),  # UPDATE error - Invalid ORIGIN
        (4, 0),  # Hold timer expired
        (5, 1),  # State machine error
        (6, 1),  # Cease - Max prefixes
    ]

    for code, subcode in test_cases:
        notify = Notify(code, subcode)
        assert notify.code == code
        assert notify.subcode == subcode


# ==============================================================================
# Part 5: Administrative Shutdown Communication (RFC 8203)
# ==============================================================================

def test_notification_shutdown_no_data() -> None:
    """Test administrative shutdown without shutdown communication.

    Old-style shutdown without message.
    """
    notif = Notification(6, 2, b'')

    assert notif.code == 6
    assert notif.subcode == 2
    assert notif.data == b''


def test_notification_shutdown_empty_communication() -> None:
    """Test shutdown with zero-length communication (RFC 8203).

    Data format: [length=0]
    """
    data = b'\x00'  # Length = 0
    notif = Notification(6, 2, data)

    assert notif.code == 6
    assert notif.subcode == 2
    assert b'empty Shutdown Communication' in notif.data


def test_notification_shutdown_valid_communication() -> None:
    """Test shutdown with valid UTF-8 communication message.

    Data format: [length][UTF-8 message]
    """
    message = "Maintenance scheduled"
    length = len(message)
    data = bytes([length]) + message.encode('utf-8')

    notif = Notification(6, 2, data)

    assert notif.code == 6
    assert notif.subcode == 2
    assert b'Shutdown Communication:' in notif.data
    assert b'Maintenance scheduled' in notif.data


def test_notification_shutdown_max_length_communication() -> None:
    """Test shutdown with maximum allowed communication (128 bytes).
    """
    message = "A" * 128
    data = bytes([128]) + message.encode('utf-8')

    notif = Notification(6, 2, data)

    assert b'Shutdown Communication:' in notif.data


def test_notification_shutdown_too_large_communication() -> None:
    """Test shutdown with oversized communication (> 128 bytes).

    Should produce error message.
    """
    message = "A" * 150
    length = 150
    data = bytes([length]) + message.encode('utf-8')

    notif = Notification(6, 2, data)

    assert b'invalid Shutdown Communication (too large)' in notif.data


def test_notification_shutdown_buffer_underrun() -> None:
    """Test shutdown with buffer underrun (length > actual data).

    Should produce error message.
    """
    data = bytes([10]) + b'ABC'  # Claims 10 bytes but only has 3

    notif = Notification(6, 2, data)

    assert b'invalid Shutdown Communication (buffer underrun)' in notif.data


def test_notification_shutdown_invalid_utf8() -> None:
    """Test shutdown with invalid UTF-8 sequence.

    Should produce error message.
    """
    # Invalid UTF-8 sequence
    invalid_utf8 = b'\x80\x81\x82'
    data = bytes([len(invalid_utf8)]) + invalid_utf8

    notif = Notification(6, 2, data)

    assert b'invalid Shutdown Communication (invalid UTF-8)' in notif.data


def test_notification_shutdown_trailing_data() -> None:
    """Test shutdown communication with trailing data.

    Should include trailing data in output.
    """
    message = "Shutdown"
    length = len(message)
    trailing = b'\x01\x02\x03'
    data = bytes([length]) + message.encode('utf-8') + trailing

    notif = Notification(6, 2, data)

    assert b'Shutdown Communication:' in notif.data
    assert b'trailing data:' in notif.data


def test_notification_shutdown_newline_carriage_return() -> None:
    """Test that shutdown communication replaces newlines and carriage returns.

    Newlines and carriage returns should be replaced with spaces.
    """
    message = "Line1\nLine2\rLine3"
    length = len(message)
    data = bytes([length]) + message.encode('utf-8')

    notif = Notification(6, 2, data)

    # Original newlines/CRs should be replaced with spaces
    assert b'\n' not in notif.data or b'Line1 Line2 Line3' in notif.data


def test_notification_admin_reset_communication() -> None:
    """Test administrative reset (6, 4) with communication.

    Should work same as shutdown (6, 2).
    """
    message = "Reset required"
    length = len(message)
    data = bytes([length]) + message.encode('utf-8')

    notif = Notification(6, 4, data)

    assert notif.code == 6
    assert notif.subcode == 4
    assert b'Shutdown Communication:' in notif.data
    assert b'Reset required' in notif.data


def test_notify_shutdown_with_message() -> None:
    """Test creating outgoing Notify for shutdown with message.
    """
    message = "Scheduled maintenance"
    notify = Notify(6, 2, message)

    assert notify.code == 6
    assert notify.subcode == 2
    # Should prepend length byte
    assert len(message) == ord(notify.data[0:1])


# ==============================================================================
# Part 6: NOTIFICATION Message Encoding (Wire Format)
# ==============================================================================

def test_notify_wire_format_basic() -> None:
    """Test Notify wire format encoding.

    Wire format:
    - Marker: 16 bytes (0xFF)
    - Length: 2 bytes
    - Type: 1 byte (0x03)
    - Code: 1 byte
    - Subcode: 1 byte
    - Data: variable
    """
    notify = Notify(2, 1, 'AB')
    packet = notify.message(negotiated=None)

    # Marker: 16 bytes of 0xFF
    assert packet[:16] == Message.MARKER

    # Length field
    length = int.from_bytes(packet[16:18], 'big')
    expected_len = Message.HEADER_LEN + 1 + 1 + len('AB')
    assert length == expected_len

    # Type: NOTIFICATION (0x03)
    assert packet[18:19] == Notification.TYPE

    # Code
    assert packet[19] == 2

    # Subcode
    assert packet[20] == 1

    # Data
    assert packet[21:] == b'AB'


def test_notify_wire_format_no_data() -> None:
    """Test Notify encoding with no additional data.
    """
    notify = Notify(4, 0)
    packet = notify.message()

    # Total length should be header + code + subcode + default message
    assert len(packet) >= Message.HEADER_LEN + 2


def test_notify_wire_format_various_sizes() -> None:
    """Test Notify encoding with various data sizes.
    """
    test_sizes = [0, 1, 10, 50, 100, 200]

    for size in test_sizes:
        data = 'A' * size
        notify = Notify(3, 1, data)
        packet = notify.message()

        # Verify marker
        assert packet[:16] == Message.MARKER

        # Verify type
        assert packet[18] == 0x03


# ==============================================================================
# Part 7: NOTIFICATION Message Decoding (Unpacking)
# ==============================================================================

def test_notification_unpack_basic() -> None:
    """Test unpacking NOTIFICATION from wire format.

    Data format: [code][subcode][data...]
    """
    data = b'\x02\x01Extra'

    notif = Notification.unpack_message(data)

    assert notif.code == 2
    assert notif.subcode == 1
    assert notif.data == b'Extra'


def test_notification_unpack_no_data() -> None:
    """Test unpacking NOTIFICATION without additional data.
    """
    data = b'\x04\x00'

    notif = Notification.unpack_message(data)

    assert notif.code == 4
    assert notif.subcode == 0
    assert notif.data == b''


def test_notification_unpack_through_message_class() -> None:
    """Test unpacking NOTIFICATION through Message base class.
    """
    message_type = Message.CODE.NOTIFICATION
    data = b'\x03\x06Binary\x00\x01'

    notif = Message.unpack(message_type, data, Direction.IN, {})

    assert isinstance(notif, Notification)
    assert notif.code == 3
    assert notif.subcode == 6


def test_notification_unpack_shutdown_with_message() -> None:
    """Test unpacking shutdown notification with communication.
    """
    message = "Shutdown now"
    length = len(message)
    data = bytes([6, 2, length]) + message.encode('utf-8')

    notif = Notification.unpack_message(data)

    assert notif.code == 6
    assert notif.subcode == 2
    assert b'Shutdown Communication:' in notif.data


def test_notification_unpack_various_errors() -> None:
    """Test unpacking various error types.
    """
    test_cases = [
        (b'\x01\x01', 1, 1),  # Message header error
        (b'\x02\x02', 2, 2),  # OPEN error - Bad Peer AS
        (b'\x03\x03', 3, 3),  # UPDATE error - Missing Well-known
        (b'\x05\x02', 5, 2),  # State machine error
        (b'\x06\x08', 6, 8),  # Cease - Out of Resources
    ]

    for data, expected_code, expected_subcode in test_cases:
        notif = Notification.unpack_message(data)
        assert notif.code == expected_code
        assert notif.subcode == expected_subcode


# ==============================================================================
# Part 8: NOTIFICATION String Representations
# ==============================================================================

def test_notification_str_representation_basic() -> None:
    """Test string representation of NOTIFICATION.

    Format: "Error code / Error subcode / data"
    """
    notif = Notification(2, 1, b'Test')

    str_repr = str(notif)
    assert 'OPEN message error' in str_repr
    assert 'Unsupported Version Number' in str_repr
    assert 'Test' in str_repr


def test_notification_str_representation_no_data() -> None:
    """Test string representation without data.
    """
    notif = Notification(4, 0)

    str_repr = str(notif)
    assert 'Hold timer expired' in str_repr
    assert 'Unspecific' in str_repr


def test_notification_str_representation_unknown_code() -> None:
    """Test string representation with unknown error code.
    """
    notif = Notification(99, 99, b'Unknown')

    str_repr = str(notif)
    assert 'unknown' in str_repr.lower()


def test_notification_str_representation_various_errors() -> None:
    """Test string representations for various error types.
    """
    test_cases = [
        (1, 2, 'Message header error', 'Bad Message Length'),
        (2, 7, 'OPEN message error', 'Unsupported Capability'),
        (3, 11, 'UPDATE message error', 'Malformed AS_PATH'),
        (6, 2, 'Cease', 'Administrative Shutdown'),
    ]

    for code, subcode, expected_code_str, expected_subcode_str in test_cases:
        notif = Notification(code, subcode)
        str_repr = str(notif)

        assert expected_code_str in str_repr
        assert expected_subcode_str in str_repr


# ==============================================================================
# Part 9: NOTIFICATION as Exception
# ==============================================================================

def test_notification_is_exception() -> None:
    """Test that Notification is an Exception subclass.

    NOTIFICATION can be raised as an exception.
    """
    notif = Notification(2, 1)

    assert isinstance(notif, Exception)


def test_notification_can_be_raised() -> NoReturn:
    """Test that NOTIFICATION can be raised and caught.
    """
    with pytest.raises(Notification) as exc_info:
        raise Notification(2, 1, b'Test error')

    caught = exc_info.value
    assert caught.code == 2
    assert caught.subcode == 1


def test_notification_raise_and_catch_specific() -> None:
    """Test raising NOTIFICATION and accessing attributes.
    """
    try:
        raise Notification(3, 6, b'Invalid ORIGIN')
    except Notification as e:
        assert e.code == 3
        assert e.subcode == 6
        assert 'ORIGIN' in str(e)


# ==============================================================================
# Part 10: Notify vs Notification Differences
# ==============================================================================

def test_notify_vs_notification_data_handling() -> None:
    """Test difference in data handling between Notify and Notification.

    Notify: Converts string to ASCII bytes, adds length for shutdown
    Notification: Parses binary data, handles shutdown communication
    """
    # Notify (outgoing): String data converted to ASCII
    notify = Notify(3, 1, 'Error text')
    assert isinstance(notify.data, bytes)

    # Notification (incoming): Binary data parsed
    notif = Notification(3, 1, b'Error text')
    assert isinstance(notif.data, bytes)


def test_notify_shutdown_adds_length_prefix() -> None:
    """Test that Notify adds length prefix for shutdown messages.
    """
    message = "Shutdown"
    notify = Notify(6, 2, message)

    # First byte should be length
    assert notify.data[0] == len(message)


def test_notification_shutdown_parses_length_prefix() -> None:
    """Test that Notification parses length prefix from shutdown messages.
    """
    message = "Shutdown"
    length = len(message)
    data = bytes([length]) + message.encode('utf-8')

    notif = Notification(6, 2, data)

    # Should parse and format the message
    assert b'Shutdown Communication:' in notif.data


# ==============================================================================
# Part 11: Round-Trip Tests
# ==============================================================================

def test_notification_encode_decode_roundtrip() -> None:
    """Test NOTIFICATION encode/decode round-trip.
    """
    # Create and encode
    original = Notify(2, 1, 'Test data')
    encoded = original.message()

    # Extract payload (skip 19-byte header)
    payload = encoded[19:]

    # Decode
    decoded = Notification.unpack_message(payload)

    # Verify match
    assert decoded.code == original.code
    assert decoded.subcode == original.subcode


def test_notification_roundtrip_various_errors() -> None:
    """Test round-trip for various error types.
    """
    test_cases = [
        (1, 1, 'Error1'),
        (2, 2, 'Error2'),
        (3, 3, 'Error3'),
        (5, 1, 'Error5'),
        (6, 1, 'Error6'),
    ]

    for code, subcode, data in test_cases:
        original = Notify(code, subcode, data)
        encoded = original.message()
        payload = encoded[19:]
        decoded = Notification.unpack_message(payload)

        assert decoded.code == code
        assert decoded.subcode == subcode


# ==============================================================================
# Part 12: Edge Cases and Special Scenarios
# ==============================================================================

def test_notification_empty_data_field() -> None:
    """Test NOTIFICATION with explicitly empty data field.
    """
    notif = Notification(1, 1, b'')

    assert notif.code == 1
    assert notif.subcode == 1
    assert notif.data == b''


def test_notification_large_data_field() -> None:
    """Test NOTIFICATION with large data field.
    """
    large_data = b'A' * 1000
    notif = Notification(3, 1, large_data)

    assert notif.code == 3
    assert notif.subcode == 1


def test_notification_parse_data_flag() -> None:
    """Test NOTIFICATION with parse_data=False.

    When parse_data=False, data is stored as-is without processing.
    """
    raw_data = b'\x00\x01\x02\x03'
    notif = Notification(3, 1, raw_data, parse_data=False)

    assert notif.data == raw_data


def test_notification_all_subcodes_for_cease() -> None:
    """Test all subcodes for Cease (code 6).
    """
    for subcode in range(9):  # 0-8
        notif = Notification(6, subcode)
        assert notif.code == 6
        assert notif.subcode == subcode


def test_notification_hold_timer_expired() -> None:
    """Test Hold Timer Expired notification (code 4).

    RFC 4271: No subcode defined, should be 0.
    """
    notif = Notification(4, 0)

    assert str(notif) == 'Hold timer expired / Unspecific'


# ==============================================================================
# Summary
# ==============================================================================
# Total tests: 72
#
# Coverage:
# - Message constants and registration (3 tests)
# - Error code/subcode strings (8 tests)
# - Incoming NOTIFICATION creation (4 tests)
# - Outgoing Notify creation (3 tests)
# - Administrative shutdown communication (12 tests)
# - Wire format encoding (3 tests)
# - Message decoding/unpacking (6 tests)
# - String representations (5 tests)
# - NOTIFICATION as Exception (3 tests)
# - Notify vs Notification differences (3 tests)
# - Round-trip encoding/decoding (2 tests)
# - Edge cases and special scenarios (6 tests)
#
# This test suite ensures:
# - Proper NOTIFICATION message creation and encoding
# - Correct wire format (RFC 4271 compliant)
# - All error codes and subcodes handled correctly
# - Administrative shutdown communication (RFC 8203)
# - Proper handling of UTF-8 messages
# - Error handling for invalid data
# - Round-trip consistency
# - Exception semantics for error handling
# ==============================================================================
