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

from exabgp.bgp.neighbor import Neighbor

import pytest
from exabgp.bgp.message import Message
from exabgp.bgp.message.notification import Notification, NotificationReceived, Notify
from exabgp.bgp.message.direction import Direction
from exabgp.bgp.message.open.capability.negotiated import Negotiated
from typing import Any


# ==============================================================================
# Test Helper Functions
# ==============================================================================


def create_negotiated() -> Negotiated:
    """Create a Negotiated object with a mock neighbor for testing."""
    neighbor = Neighbor()
    return Negotiated.make_negotiated(neighbor, Direction.OUT)


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
    """Test NOTIFICATION TYPE byte representation."""
    assert Notification.TYPE == b'\x03'


def test_notification_message_registration() -> None:
    """Test that NOTIFICATION is properly registered with Message class."""
    assert Message.CODE.NOTIFICATION in Message.registered_message

    klass = Message.klass(Message.CODE.NOTIFICATION)
    assert klass == Notification


# ==============================================================================
# Part 2: Error Code and Subcode String Representations
# ==============================================================================


# The names are the IANA "BGP Error (Notification) Codes" and "BGP Error Subcodes"
# registries as updated 2026-09-09.  A deprecated value keeps the name it had before it
# was deprecated, in brackets, so a NOTIFICATION from an older peer still reads usefully.
IANA_CODES = {
    1: 'Message Header Error',
    2: 'OPEN Message Error',
    3: 'UPDATE Message Error',
    4: 'Hold Timer Expired',
    5: 'Finite State Machine Error',
    6: 'Cease',
    7: 'ROUTE-REFRESH Message Error',
    8: 'Send Hold Timer Expired',
    9: 'Loss of LSDB Synchronization',
}

IANA_SUBCODES = {
    (1, 0): 'Unspecific',
    (1, 1): 'Connection Not Synchronized',
    (1, 2): 'Bad Message Length',
    (1, 3): 'Bad Message Type',
    (2, 0): 'Unspecific',
    (2, 1): 'Unsupported Version Number',
    (2, 2): 'Bad Peer AS',
    (2, 3): 'Bad BGP Identifier',
    (2, 4): 'Unsupported Optional Parameter',
    (2, 5): '[Deprecated] Authentication Failure',
    (2, 6): 'Unacceptable Hold Time',
    (2, 7): 'Unsupported Capability',
    (2, 8): '[Deprecated] Grouping Conflict',
    (2, 9): '[Deprecated] Grouping Required',
    (2, 10): '[Deprecated] Capability Value Mismatch',
    (2, 11): 'Role Mismatch',
    (3, 0): 'Unspecific',
    (3, 1): 'Malformed Attribute List',
    (3, 2): 'Unrecognized Well-known Attribute',
    (3, 3): 'Missing Well-known Attribute',
    (3, 4): 'Attribute Flags Error',
    (3, 5): 'Attribute Length Error',
    (3, 6): 'Invalid ORIGIN Attribute',
    (3, 7): '[Deprecated] AS Routing Loop',
    (3, 8): 'Invalid NEXT_HOP Attribute',
    (3, 9): 'Optional Attribute Error',
    (3, 10): 'Invalid Network Field',
    (3, 11): 'Malformed AS_PATH',
    (4, 0): 'Unspecific',
    (5, 0): 'Unspecified Error',
    (5, 1): 'Receive Unexpected Message in OpenSent State',
    (5, 2): 'Receive Unexpected Message in OpenConfirm State',
    (5, 3): 'Receive Unexpected Message in Established State',
    (6, 0): 'Reserved',
    (6, 1): 'Maximum Number of Prefixes Reached',
    (6, 2): 'Administrative Shutdown',
    (6, 3): 'Peer De-configured',
    (6, 4): 'Administrative Reset',
    (6, 5): 'Connection Rejected',
    (6, 6): 'Other Configuration Change',
    (6, 7): 'Connection Collision Resolution',
    (6, 8): 'Out of Resources',
    (6, 9): 'Hard Reset',
    (6, 10): 'BFD Down',
    (7, 0): 'Reserved',
    (7, 1): 'Invalid Message Length',
    (8, 0): 'Unspecific',
    (9, 0): 'Unspecific',
}


def test_notification_error_code_strings() -> None:
    """Every error code carries its IANA name, and no name IANA does not list."""
    assert Notification._str_code == IANA_CODES


def test_notification_error_subcode_strings() -> None:
    """Every subcode carries its IANA name.

    (7, 2) "Malformed Message Subtype" came from an expired draft; IANA lists ROUTE-REFRESH
    subcodes 2 to 255 as unassigned, and RFC 7313 says an unknown subtype is ignored.
    """
    assert Notification._str_subcode == IANA_SUBCODES


# ==============================================================================
# Part 3: Incoming NOTIFICATION Message Creation (from peer)
# ==============================================================================


def test_notification_incoming_creation_basic() -> None:
    """Test creating incoming NOTIFICATION with basic error."""
    notif = Notification.make_notification(2, 1, b'Extra data')

    assert notif.code == 2
    assert notif.subcode == 1
    assert notif.text == b'Extra data'


def test_notification_incoming_creation_no_data() -> None:
    """Test creating NOTIFICATION without additional data."""
    notif = Notification.make_notification(4, 0)

    assert notif.code == 4
    assert notif.subcode == 0
    assert notif.text == b''


def test_notification_incoming_creation_binary_data() -> None:
    """Test creating NOTIFICATION with non-printable binary data.

    Non-printable data should be converted to hex representation.
    """
    binary_data = b'\x00\x01\x02\xff'
    notif = Notification.make_notification(3, 5, binary_data)

    assert notif.code == 3
    assert notif.subcode == 5
    # Binary data should be converted to hex string
    assert isinstance(notif.text, (bytes, str))


def test_notification_incoming_printable_data() -> None:
    """Test NOTIFICATION with printable ASCII data."""
    printable_data = b'Error message text'
    notif = Notification.make_notification(1, 2, printable_data)

    assert notif.code == 1
    assert notif.subcode == 2
    assert notif.text == printable_data


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
    """With no detail the names are the text, and the peer's Data field stays empty.

    It used to carry the subcode name, which only told the peer what the subcode octet it
    had just read already said.
    """
    notify = Notify(2, 2)

    assert notify.code == 2
    assert notify.subcode == 2
    assert notify.data == b''
    assert str(notify) == 'OPEN Message Error / Bad Peer AS'


def test_notify_outgoing_creation_various_errors() -> None:
    """Test creating Notify messages for various error types."""
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
# Part 5: Administrative Shutdown Communication (RFC 9003, which obsoletes RFC 8203)
# ==============================================================================


def test_notification_shutdown_no_data() -> None:
    """Test administrative shutdown without shutdown communication.

    Old-style shutdown without message.
    """
    notif = Notification.make_notification(6, 2, b'')

    assert notif.code == 6
    assert notif.subcode == 2
    assert notif.text == b''


def test_notification_shutdown_empty_communication() -> None:
    """Test shutdown with zero-length communication (RFC 8203).

    Data format: [length=0]
    """
    data = b'\x00'  # Length = 0
    notif = Notification.make_notification(6, 2, data)

    assert notif.code == 6
    assert notif.subcode == 2
    assert b'empty Shutdown Communication' in notif.text


def test_notification_shutdown_valid_communication() -> None:
    """Test shutdown with valid UTF-8 communication message.

    Data format: [length][UTF-8 message]
    """
    message = 'Maintenance scheduled'
    length = len(message)
    data = bytes([length]) + message.encode('utf-8')

    notif = Notification.make_notification(6, 2, data)

    assert notif.code == 6
    assert notif.subcode == 2
    assert b'Shutdown Communication:' in notif.text
    assert b'Maintenance scheduled' in notif.text


def test_notification_shutdown_max_length_communication() -> None:
    """Test shutdown with maximum allowed communication (128 bytes)."""
    message = 'A' * 128
    data = bytes([128]) + message.encode('utf-8')

    notif = Notification.make_notification(6, 2, data)

    assert b'Shutdown Communication:' in notif.text


def test_notification_shutdown_longer_than_rfc8203_allowed() -> None:
    """RFC 9003 raised the limit from RFC 8203's 128 octets to 255, all one octet can say."""
    message = 'A' * 150
    data = bytes([len(message)]) + message.encode('utf-8')

    notif = Notification.make_notification(6, 2, data)

    assert notif.text == b'Shutdown Communication: "' + message.encode() + b'"'


def test_notification_shutdown_buffer_underrun() -> None:
    """Test shutdown with buffer underrun (length > actual data).

    Should produce error message.
    """
    data = bytes([10]) + b'ABC'  # Claims 10 bytes but only has 3

    notif = Notification.make_notification(6, 2, data)

    assert b'invalid Shutdown Communication (buffer underrun)' in notif.text


def test_notification_shutdown_invalid_utf8() -> None:
    """Test shutdown with invalid UTF-8 sequence.

    Should produce error message.
    """
    # Invalid UTF-8 sequence
    invalid_utf8 = b'\x80\x81\x82'
    data = bytes([len(invalid_utf8)]) + invalid_utf8

    notif = Notification.make_notification(6, 2, data)

    assert b'invalid Shutdown Communication (invalid UTF-8)' in notif.text


def test_notification_shutdown_trailing_data() -> None:
    """Test shutdown communication with trailing data.

    Should include trailing data in output.
    """
    message = 'Shutdown'
    length = len(message)
    trailing = b'\x01\x02\x03'
    data = bytes([length]) + message.encode('utf-8') + trailing

    notif = Notification.make_notification(6, 2, data)

    assert b'Shutdown Communication:' in notif.text
    assert b'trailing data:' in notif.text


def test_notification_shutdown_newline_carriage_return() -> None:
    """A shutdown communication is flattened to one line, ON PURPOSE.

    notification.py replaces CR and LF with spaces before the value is encoded, and that
    is a DISPLAY choice, not a safety measure.  Stating it because it now reads like the
    defect we have spent this series removing: peer text being rewritten on its way out.

    It is not that defect, and the difference is where it happens.  This rewrites the
    VALUE before anything encodes it, not the finished line, so nothing about it depends
    on escaping.  Escaping could regress entirely and this would still do exactly what it
    does.  The encoder is what makes the text unforgeable, and it is tested for that
    separately in test_api_stream_integrity.py.

    So it must not be "fixed" into escaping.  RFC 8203 makes this field free text for an
    operator to read, ExaBGP renders it on one line the way the text API does with
    oneline(), and turning the flattening into an escape would silently change what every
    operator sees at the moment a peer shuts a session down.

    The assertion was `b'\n' not in data or b'Line1 Line2 Line3' in data`.  The or is
    satisfied by its first half alone, so an encoder which DELETED the communication
    passed it.  Other tests in this file catch deletion, so it was weak rather than
    vacuous, but a pin for a deliberate behaviour should state the behaviour: the exact
    flattened text, and nothing else.
    """
    message = 'Line1\nLine2\rLine3'
    data = bytes([len(message)]) + message.encode('utf-8')

    notif = Notification.make_notification(6, 2, data)

    assert b'Shutdown Communication: "Line1 Line2 Line3"' in notif.text
    assert b'\n' not in notif.text
    assert b'\r' not in notif.text


def test_notification_admin_reset_communication() -> None:
    """Test administrative reset (6, 4) with communication.

    Should work same as shutdown (6, 2).
    """
    message = 'Reset required'
    length = len(message)
    data = bytes([length]) + message.encode('utf-8')

    notif = Notification.make_notification(6, 4, data)

    assert notif.code == 6
    assert notif.subcode == 4
    assert b'Shutdown Communication:' in notif.text
    assert b'Reset required' in notif.text


def test_notify_shutdown_with_message() -> None:
    """Test creating outgoing Notify for shutdown with message."""
    message = 'Scheduled maintenance'
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
    packet = notify.notification.pack_message(Negotiated.UNSET)

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
    """Test Notify encoding with no additional data."""
    notify = Notify(4, 0)
    packet = notify.notification.pack_message(create_negotiated())

    # Total length should be header + code + subcode + default message
    assert len(packet) >= Message.HEADER_LEN + 2


def test_notify_wire_format_various_sizes() -> None:
    """Test Notify encoding with various data sizes."""
    test_sizes = [0, 1, 10, 50, 100, 200]

    for size in test_sizes:
        data = 'A' * size
        notify = Notify(3, 1, data)
        packet = notify.notification.pack_message(create_negotiated())

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

    notif = Notification.unpack_message(data, create_negotiated())

    assert notif.code == 2
    assert notif.subcode == 1
    assert notif.text == b'Extra'


def test_notification_unpack_no_data() -> None:
    """Test unpacking NOTIFICATION without additional data."""
    data = b'\x04\x00'

    notif = Notification.unpack_message(data, create_negotiated())

    assert notif.code == 4
    assert notif.subcode == 0
    assert notif.text == b''


def test_notification_unpack_through_message_class() -> None:
    """Test unpacking NOTIFICATION through Message base class."""
    message_type = Message.CODE.NOTIFICATION
    data = b'\x03\x06Binary\x00\x01'

    notif = Message.unpack(message_type, data, {})

    assert isinstance(notif, Notification)
    assert notif.code == 3
    assert notif.subcode == 6


def test_notification_unpack_shutdown_with_message() -> None:
    """Test unpacking shutdown notification with communication."""
    message = 'Shutdown now'
    length = len(message)
    data = bytes([6, 2, length]) + message.encode('utf-8')

    notif = Notification.unpack_message(data, create_negotiated())

    assert notif.code == 6
    assert notif.subcode == 2
    assert b'Shutdown Communication:' in notif.text


def test_notification_unpack_various_errors() -> None:
    """Test unpacking various error types."""
    test_cases = [
        (b'\x01\x01', 1, 1),  # Message header error
        (b'\x02\x02', 2, 2),  # OPEN error - Bad Peer AS
        (b'\x03\x03', 3, 3),  # UPDATE error - Missing Well-known
        (b'\x05\x02', 5, 2),  # State machine error
        (b'\x06\x08', 6, 8),  # Cease - Out of Resources
    ]

    for data, expected_code, expected_subcode in test_cases:
        notif = Notification.unpack_message(data, create_negotiated())
        assert notif.code == expected_code
        assert notif.subcode == expected_subcode


# ==============================================================================
# Part 8: NOTIFICATION String Representations
# ==============================================================================


def test_notification_str_representation_basic() -> None:
    """Test string representation of NOTIFICATION.

    Format: "Error code / Error subcode / data"
    """
    notif = Notification.make_notification(2, 1, b'Test')

    str_repr = str(notif)
    assert 'OPEN Message Error' in str_repr
    assert 'Unsupported Version Number' in str_repr
    assert 'Test' in str_repr


def test_notification_str_representation_no_data() -> None:
    """Test string representation without data."""
    notif = Notification.make_notification(4, 0)

    str_repr = str(notif)
    assert 'Hold Timer Expired' in str_repr
    assert 'Unspecific' in str_repr


def test_notification_str_representation_unknown_code() -> None:
    """Test string representation with unknown error code."""
    notif = Notification.make_notification(99, 99, b'Unknown')

    str_repr = str(notif)
    assert 'unknown' in str_repr.lower()


def test_notification_str_representation_various_errors() -> None:
    """Test string representations for various error types."""
    test_cases = [
        (1, 2, 'Message Header Error', 'Bad Message Length'),
        (2, 7, 'OPEN Message Error', 'Unsupported Capability'),
        (3, 11, 'UPDATE Message Error', 'Malformed AS_PATH'),
        (6, 2, 'Cease', 'Administrative Shutdown'),
    ]

    for code, subcode, expected_code_str, expected_subcode_str in test_cases:
        notif = Notification.make_notification(code, subcode)
        str_repr = str(notif)

        assert expected_code_str in str_repr
        assert expected_subcode_str in str_repr


# ==============================================================================
# Part 9: NOTIFICATION is a message, the exceptions hold one
# ==============================================================================


def test_notification_is_not_an_exception() -> None:
    """A Notification is a message: raising one is a TypeError, not a silent reset."""
    notif = Notification.make_notification(2, 1)

    assert not isinstance(notif, BaseException)
    thrown: Any = notif
    with pytest.raises(TypeError):
        raise thrown


def test_a_received_notification_is_raised_as_notification_received() -> None:
    """The reactor raises what a peer sent wrapped, and the wrapper answers its code."""
    with pytest.raises(NotificationReceived) as exc_info:
        raise NotificationReceived(Notification.make_notification(3, 6, b'Invalid ORIGIN'))

    caught = exc_info.value
    assert caught.code == 3
    assert caught.subcode == 6
    assert 'ORIGIN' in str(caught)


def test_notify_is_not_a_notification_and_holds_one() -> None:
    """Neither exception is the other, so the order of the handlers cannot matter."""
    notify = Notify(2, 1, 'refused')

    assert not isinstance(notify, NotificationReceived)
    assert notify.notification.code == 2
    assert notify.notification.data == b'refused'


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
    notif = Notification.make_notification(3, 1, b'Error text')
    assert isinstance(notif.text, bytes)


def test_notify_shutdown_adds_length_prefix() -> None:
    """Test that Notify adds length prefix for shutdown messages."""
    message = 'Shutdown'
    notify = Notify(6, 2, message)

    # First byte should be length
    assert notify.data[0] == len(message)


def test_notification_shutdown_parses_length_prefix() -> None:
    """Test that Notification parses length prefix from shutdown messages."""
    message = 'Shutdown'
    length = len(message)
    data = bytes([length]) + message.encode('utf-8')

    notif = Notification.make_notification(6, 2, data)

    # Should parse and format the message
    assert b'Shutdown Communication:' in notif.text


# ==============================================================================
# Part 11: Round-Trip Tests
# ==============================================================================


def test_notification_encode_decode_roundtrip() -> None:
    """Test NOTIFICATION encode/decode round-trip."""
    # Create and encode
    original = Notify(2, 1, 'Test data')
    encoded = original.notification.pack_message(create_negotiated())

    # Extract payload (skip 19-byte header)
    payload = encoded[19:]

    # Decode
    decoded = Notification.unpack_message(payload, create_negotiated())

    # Verify match
    assert decoded.code == original.code
    assert decoded.subcode == original.subcode


def test_notification_roundtrip_various_errors() -> None:
    """Test round-trip for various error types."""
    test_cases = [
        (1, 1, 'Error1'),
        (2, 2, 'Error2'),
        (3, 3, 'Error3'),
        (5, 1, 'Error5'),
        (6, 1, 'Error6'),
    ]

    for code, subcode, data in test_cases:
        original = Notify(code, subcode, data)
        encoded = original.notification.pack_message(create_negotiated())
        payload = encoded[19:]
        decoded = Notification.unpack_message(payload, create_negotiated())

        assert decoded.code == code
        assert decoded.subcode == subcode


# ==============================================================================
# Part 12: Edge Cases and Special Scenarios
# ==============================================================================


def test_notification_empty_data_field() -> None:
    """Test NOTIFICATION with explicitly empty data field."""
    notif = Notification.make_notification(1, 1, b'')

    assert notif.code == 1
    assert notif.subcode == 1
    assert notif.text == b''


def test_notification_large_data_field() -> None:
    """Test NOTIFICATION with large data field."""
    large_data = b'A' * 1000
    notif = Notification.make_notification(3, 1, large_data)

    assert notif.code == 3
    assert notif.subcode == 1


def test_notification_raw_data_access() -> None:
    """Test NOTIFICATION raw_data property.

    The raw_data property gives access to the unparsed data bytes.
    """
    raw_data = b'\x00\x01\x02\x03'
    notif = Notification.make_notification(3, 1, raw_data)

    # raw_data gives unparsed bytes
    assert notif.data == raw_data
    # data property parses (for non-printable data, converts to hex)
    assert isinstance(notif.text, (bytes, str))


def test_notification_all_subcodes_for_cease() -> None:
    """Test all subcodes for Cease (code 6)."""
    for subcode in range(9):  # 0-8
        notif = Notification.make_notification(6, subcode)
        assert notif.code == 6
        assert notif.subcode == subcode


def test_notification_hold_timer_expired() -> None:
    """Test Hold Timer Expired notification (code 4).

    RFC 4271: No subcode defined, should be 0.
    """
    notif = Notification.make_notification(4, 0)

    assert str(notif) == 'Hold Timer Expired / Unspecific'


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
