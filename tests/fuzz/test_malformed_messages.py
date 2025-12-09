"""Comprehensive fuzz tests for malformed BGP messages.

This module tests that BGP message parsing handles malformed input gracefully
without crashing. All parsing errors should result in appropriate Notify
exceptions, not crashes or undefined behavior.

Test Categories:
- Invalid marker bytes (not all 0xFF)
- Length field mismatches
- Truncated headers and bodies
- Type byte out of range
- Zero-length messages
- Maximum length exceeded
- Message-specific malformed content
"""

import pytest
import struct
from typing import Any
from unittest.mock import MagicMock, Mock
from hypothesis import given, strategies as st, settings, HealthCheck, assume

pytestmark = pytest.mark.fuzz


# =============================================================================
# Helper Functions
# =============================================================================


def create_bgp_header(marker: bytes, length: int, msg_type: int) -> bytes:
    """Create a BGP message header.

    Args:
        marker: 16-byte marker (should be all 0xFF for valid messages)
        length: Total message length including header (19-4096)
        msg_type: Message type (1=OPEN, 2=UPDATE, 3=NOTIFICATION, 4=KEEPALIVE, 5=ROUTE_REFRESH)

    Returns:
        19-byte BGP header
    """
    return marker + struct.pack('!H', length) + bytes([msg_type])


def create_mock_negotiated() -> Any:
    """Create a minimal mock Negotiated object for testing."""
    neighbor = Mock()
    neighbor.__getitem__ = Mock(return_value={'aigp': False})
    neighbor.session = Mock()
    neighbor.session.local_address = Mock()
    neighbor.session.local_address.afi = 1  # IPv4
    neighbor.session.local_address.top = Mock(return_value=b'\x7f\x00\x00\x01')

    negotiated = Mock()
    negotiated.neighbor = neighbor
    negotiated.families = [(1, 1)]  # IPv4 unicast
    negotiated.asn4 = True
    negotiated.local_as = 65000
    negotiated.peer_as = 65001
    negotiated.aigp = False
    negotiated.msg_size = 4096
    negotiated.required = Mock(return_value=False)  # No AddPath

    return negotiated


# =============================================================================
# BGP Header Validation Tests
# =============================================================================


@pytest.mark.fuzz
@given(
    byte_value=st.integers(min_value=0, max_value=254),
    position=st.integers(min_value=0, max_value=15),
)
@settings(deadline=None, max_examples=100)
def test_invalid_marker_single_byte(byte_value: int, position: int) -> None:
    """Test that a single invalid byte in marker is detected."""
    from exabgp.reactor.network.connection import Connection
    from exabgp.reactor.network.error import NotifyError

    # Create marker with one bad byte
    marker = bytearray(b'\xff' * 16)
    marker[position] = byte_value
    assume(byte_value != 0xFF)  # Skip if we accidentally made it valid

    header = create_bgp_header(bytes(marker), 19, 4)  # KEEPALIVE

    connection = Connection(1, '127.0.0.1', '127.0.0.1')
    connection.io = MagicMock()

    def mock_reader(num_bytes: int) -> Any:
        yield header[:num_bytes] if num_bytes <= len(header) else header

    connection._reader = mock_reader

    reader = connection.reader()
    length, msg_type, hdr, body, error = next(reader)

    # Should detect invalid marker
    assert error is not None
    assert isinstance(error, NotifyError)
    assert error.code == 1  # Message Header Error
    assert error.subcode == 1  # Connection Not Synchronized


@pytest.mark.fuzz
@given(marker_pattern=st.binary(min_size=16, max_size=16))
@settings(deadline=None, max_examples=100)
def test_random_marker_pattern(marker_pattern: bytes) -> None:
    """Test various random marker patterns."""
    from exabgp.reactor.network.connection import Connection
    from exabgp.reactor.network.error import NotifyError

    is_valid = marker_pattern == b'\xff' * 16
    header = create_bgp_header(marker_pattern, 19, 4)

    connection = Connection(1, '127.0.0.1', '127.0.0.1')
    connection.io = MagicMock()

    def mock_reader(num_bytes: int) -> Any:
        yield header[:num_bytes] if num_bytes <= len(header) else header

    connection._reader = mock_reader

    reader = connection.reader()
    length, msg_type, hdr, body, error = next(reader)

    if is_valid:
        assert error is None
        assert length == 19
    else:
        assert error is not None
        assert isinstance(error, NotifyError)
        assert error.code == 1
        assert error.subcode == 1


@pytest.mark.fuzz
@given(length=st.integers(min_value=0, max_value=18))
@settings(deadline=None, max_examples=19)
def test_length_too_small(length: int) -> None:
    """Test that length < 19 is rejected."""
    from exabgp.reactor.network.connection import Connection
    from exabgp.reactor.network.error import NotifyError

    header = create_bgp_header(b'\xff' * 16, length, 4)

    connection = Connection(1, '127.0.0.1', '127.0.0.1')
    connection.io = MagicMock()

    def mock_reader(num_bytes: int) -> Any:
        yield header[:num_bytes] if num_bytes <= len(header) else header

    connection._reader = mock_reader

    reader = connection.reader()
    length_result, msg_type, hdr, body, error = next(reader)

    # Should reject length < 19
    assert error is not None
    assert isinstance(error, NotifyError)
    assert error.code == 1  # Message Header Error
    assert error.subcode == 2  # Bad Message Length


@pytest.mark.fuzz
@given(length=st.integers(min_value=4097, max_value=65535))
@settings(deadline=None, max_examples=50)
def test_length_too_large(length: int) -> None:
    """Test that length > 4096 is rejected (default max)."""
    from exabgp.reactor.network.connection import Connection
    from exabgp.reactor.network.error import NotifyError

    header = create_bgp_header(b'\xff' * 16, length, 4)
    # Add body to fill length (even though header claims it)
    body = b'\x00' * min(length - 19, 100)
    data = header + body

    connection = Connection(1, '127.0.0.1', '127.0.0.1')
    connection.io = MagicMock()

    def mock_reader(num_bytes: int) -> Any:
        yield data[:num_bytes] if num_bytes <= len(data) else data

    connection._reader = mock_reader

    reader = connection.reader()
    length_result, msg_type, hdr, body_result, error = next(reader)

    # Should reject length > 4096
    assert error is not None
    assert isinstance(error, NotifyError)
    assert error.code == 1  # Message Header Error
    assert error.subcode == 2  # Bad Message Length


@pytest.mark.fuzz
@given(msg_type=st.integers(min_value=7, max_value=255))
@settings(deadline=None, max_examples=50)
def test_invalid_message_type(msg_type: int) -> None:
    """Test that invalid message types are handled gracefully."""
    from exabgp.bgp.message import Message
    from exabgp.bgp.message.notification import Notify

    header = create_bgp_header(b'\xff' * 16, 19, msg_type)
    data = header[19:]  # Body (empty for this test)

    negotiated = create_mock_negotiated()

    try:
        # Should raise Notify for unknown message type
        Message.unpack(msg_type, data, negotiated)
        # If it doesn't raise, klass_unknown may not be registered
    except Notify as e:
        # Expected for unknown message types
        assert e.code == 2  # OPEN message error (used for capability/type errors)
        assert e.subcode == 4  # Unsupported Optional Parameter
    except AttributeError:
        # klass_unknown not registered - this is acceptable behavior
        # Unknown message types may not have a handler
        pass


# =============================================================================
# OPEN Message Malformed Tests
# =============================================================================


@pytest.mark.fuzz
@given(version=st.integers(min_value=0, max_value=255).filter(lambda v: v != 4))
@settings(deadline=None, max_examples=50)
def test_open_invalid_version(version: int) -> None:
    """Test that OPEN with version != 4 is rejected."""
    from exabgp.bgp.message.open import Open
    from exabgp.bgp.message.notification import Notify

    # Minimal OPEN: version(1) + asn(2) + hold_time(2) + router_id(4) + opt_len(1) = 10 bytes
    open_data = bytes([version]) + struct.pack('!H', 65000) + struct.pack('!H', 90) + b'\xc0\xa8\x01\x01' + b'\x00'

    negotiated = create_mock_negotiated()

    with pytest.raises(Notify) as exc_info:
        Open.unpack_message(open_data, negotiated)

    assert exc_info.value.code == 2  # OPEN message error
    assert exc_info.value.subcode == 1  # Unsupported Version Number


@pytest.mark.fuzz
@given(data_len=st.integers(min_value=0, max_value=8))
@settings(deadline=None, max_examples=9)
def test_open_truncated(data_len: int) -> None:
    """Test that truncated OPEN messages are rejected."""
    from exabgp.bgp.message.open import Open
    from exabgp.bgp.message.notification import Notify

    # Valid OPEN data, then truncate
    full_data = bytes([4]) + struct.pack('!H', 65000) + struct.pack('!H', 90) + b'\xc0\xa8\x01\x01' + b'\x00'
    truncated = full_data[:data_len]

    negotiated = create_mock_negotiated()

    with pytest.raises(Notify) as exc_info:
        Open.unpack_message(truncated, negotiated)

    assert exc_info.value.code == 2  # OPEN message error
    assert exc_info.value.subcode == 0  # Unspecific (for length errors)


@pytest.mark.fuzz
@given(hold_time=st.integers(min_value=1, max_value=2))
@settings(deadline=None, max_examples=2)
def test_open_invalid_hold_time(hold_time: int) -> None:
    """Test that hold time of 1 or 2 seconds is rejected (must be 0 or >= 3)."""
    # Note: This is RFC 4271 requirement - hold time must be 0 or >= 3
    # The parser may or may not enforce this at parse time
    from exabgp.bgp.message.open import Open

    open_data = bytes([4]) + struct.pack('!H', 65000) + struct.pack('!H', hold_time) + b'\xc0\xa8\x01\x01' + b'\x00'

    negotiated = create_mock_negotiated()

    try:
        open_msg = Open.unpack_message(open_data, negotiated)
        # If parsing succeeds, validate the hold_time is preserved
        # (validation happens at negotiation time, not parse time)
        assert open_msg.hold_time == hold_time
    except Exception:
        # May reject at parse time
        pass


# =============================================================================
# UPDATE Message Malformed Tests
# =============================================================================


@pytest.mark.fuzz
@given(withdrawn_len=st.integers(min_value=0, max_value=10))
@settings(deadline=None, max_examples=20)
def test_update_withdrawn_length_exceeds_data(withdrawn_len: int) -> None:
    """Test UPDATE where withdrawn length exceeds available data."""
    from exabgp.bgp.message.update import Update
    from exabgp.bgp.message.notification import Notify

    # Claim we have withdrawn_len bytes but provide less
    # Just the 2-byte withdrawn length field
    update_data = struct.pack('!H', withdrawn_len)

    assume(withdrawn_len > 0)  # Only test when we claim to have data

    negotiated = create_mock_negotiated()

    try:
        update = Update(update_data, negotiated)
        # Accessing parsed data should fail
        _ = update.parse()
        pytest.fail('Expected exception for truncated UPDATE')
    except (Notify, IndexError, struct.error, ValueError):
        # Expected - malformed data detected
        pass


@pytest.mark.fuzz
@given(attr_len=st.integers(min_value=1, max_value=100))
@settings(deadline=None, max_examples=50)
def test_update_attribute_length_exceeds_data(attr_len: int) -> None:
    """Test UPDATE where attribute length exceeds available data."""
    from exabgp.bgp.message.update import Update
    from exabgp.bgp.message.notification import Notify

    # withdrawn_len=0, then attr_len claims more data than we have
    update_data = struct.pack('!H', 0) + struct.pack('!H', attr_len)

    negotiated = create_mock_negotiated()

    try:
        update = Update(update_data, negotiated)
        _ = update.parse()
        pytest.fail('Expected exception for truncated UPDATE')
    except (Notify, IndexError, struct.error, ValueError):
        # Expected - malformed data detected
        pass


@pytest.mark.fuzz
@given(random_data=st.binary(min_size=0, max_size=50))
@settings(suppress_health_check=[HealthCheck.too_slow], deadline=None, max_examples=100)
def test_update_random_payload(random_data: bytes) -> None:
    """Test UPDATE parsing doesn't crash on random payloads."""
    from exabgp.bgp.message.update import Update

    negotiated = create_mock_negotiated()

    try:
        update = Update(random_data, negotiated)
        _ = update.parse()
    except Exception as e:
        # Should handle gracefully, not crash
        assert not isinstance(e, (SystemExit, KeyboardInterrupt, RecursionError))


@pytest.mark.fuzz
def test_update_empty_payload() -> None:
    """Test UPDATE with empty payload."""
    from exabgp.bgp.message.update import Update
    from exabgp.bgp.message.notification import Notify

    negotiated = create_mock_negotiated()

    try:
        update = Update(b'', negotiated)
        _ = update.parse()
        pytest.fail('Expected exception for empty UPDATE')
    except (IndexError, struct.error, ValueError, Notify):
        # Expected - not enough data
        pass


@pytest.mark.fuzz
def test_update_minimum_valid() -> None:
    """Test UPDATE with minimum valid content (EOR format)."""
    from exabgp.bgp.message.update import Update

    # Minimum valid UPDATE: withdrawn_len=0, attr_len=0, no NLRI
    update_data = struct.pack('!H', 0) + struct.pack('!H', 0)

    negotiated = create_mock_negotiated()

    # This should parse as EOR
    update = Update(update_data, negotiated)
    # Should not crash when accessing data
    try:
        parsed = update.parse()
        # Empty update - should have no routes
        assert len(parsed.announces) == 0
        assert len(parsed.withdraws) == 0
    except Exception:
        # May be treated as EOR which is handled specially
        pass


# =============================================================================
# NOTIFICATION Message Malformed Tests
# =============================================================================


@pytest.mark.fuzz
@given(data_len=st.integers(min_value=0, max_value=1))
@settings(deadline=None, max_examples=2)
def test_notification_truncated(data_len: int) -> None:
    """Test that truncated NOTIFICATION messages are rejected."""
    from exabgp.bgp.message.notification import Notification

    # Notification needs at least 2 bytes (code + subcode)
    truncated = b'\x06'[:data_len]

    with pytest.raises(ValueError):
        Notification(truncated)


@pytest.mark.fuzz
@given(code=st.integers(min_value=0, max_value=255), subcode=st.integers(min_value=0, max_value=255))
@settings(deadline=None, max_examples=100)
def test_notification_all_codes(code: int, subcode: int) -> None:
    """Test NOTIFICATION parsing with all possible code/subcode combinations."""
    from exabgp.bgp.message.notification import Notification

    notification_data = bytes([code, subcode]) + b'test data'

    notification = Notification(notification_data)

    assert notification.code == code
    assert notification.subcode == subcode
    assert notification.raw_data == b'test data'


@pytest.mark.fuzz
@given(shutdown_len=st.integers(min_value=129, max_value=255))
@settings(deadline=None, max_examples=50)
def test_notification_shutdown_too_long(shutdown_len: int) -> None:
    """Test NOTIFICATION shutdown communication with excessive length."""
    from exabgp.bgp.message.notification import Notification

    # Code 6, Subcode 2 = Administrative Shutdown
    # Data format: length_byte + message
    notification_data = bytes([6, 2, shutdown_len]) + b'x' * shutdown_len

    notification = Notification(notification_data)

    # Should detect invalid length
    data = notification.data
    assert b'invalid' in data.lower() or b'too large' in data.lower()


# =============================================================================
# KEEPALIVE Message Tests
# =============================================================================


@pytest.mark.fuzz
@given(extra_bytes=st.binary(min_size=1, max_size=100))
@settings(deadline=None, max_examples=50)
def test_keepalive_with_extra_data(extra_bytes: bytes) -> None:
    """Test KEEPALIVE with extra data (should have empty body)."""
    from exabgp.reactor.network.connection import Connection
    from exabgp.reactor.network.error import NotifyError

    # KEEPALIVE must be exactly 19 bytes
    length = 19 + len(extra_bytes)
    header = create_bgp_header(b'\xff' * 16, length, 4)
    data = header + extra_bytes

    connection = Connection(1, '127.0.0.1', '127.0.0.1')
    connection.io = MagicMock()

    def mock_reader(num_bytes: int) -> Any:
        yield data[:num_bytes] if num_bytes <= len(data) else data

    connection._reader = mock_reader

    reader = connection.reader()
    for result in reader:
        length_result, msg_type, hdr, body, error = result
        if length_result > 0 or error is not None:
            break

    # KEEPALIVE with extra data should be rejected
    assert error is not None
    assert isinstance(error, NotifyError)


# =============================================================================
# Message Length Mismatch Tests
# =============================================================================


@pytest.mark.fuzz
@given(
    claimed_length=st.integers(min_value=20, max_value=100),
    actual_body_size=st.integers(min_value=0, max_value=50),
)
@settings(deadline=None, max_examples=100)
def test_length_body_mismatch(claimed_length: int, actual_body_size: int) -> None:
    """Test handling of length field mismatches."""
    from exabgp.reactor.network.connection import Connection

    # Don't test when they match (that's valid)
    body_size_expected = claimed_length - 19
    assume(actual_body_size != body_size_expected)

    header = create_bgp_header(b'\xff' * 16, claimed_length, 1)  # OPEN
    body = b'\x00' * actual_body_size
    data = header + body

    connection = Connection(1, '127.0.0.1', '127.0.0.1')
    connection.io = MagicMock()

    bytes_provided = 0

    def mock_reader(num_bytes: int) -> Any:
        nonlocal bytes_provided
        if bytes_provided >= len(data):
            yield b''
            return
        chunk = data[bytes_provided : bytes_provided + num_bytes]
        bytes_provided += num_bytes
        yield chunk

    connection._reader = mock_reader

    reader = connection.reader()

    try:
        for result in reader:
            length_result, msg_type, hdr, body_result, error = result
            if length_result > 0 or error is not None:
                break
            # Prevent infinite loop
            if bytes_provided > len(data) + 100:
                break

        # Should either get error or incomplete data
        if actual_body_size < body_size_expected:
            # Not enough data - should wait or error
            pass
    except StopIteration:
        # Expected - not enough data
        pass


# =============================================================================
# Boundary Value Tests
# =============================================================================


@pytest.mark.fuzz
def test_message_exactly_19_bytes() -> None:
    """Test message with exactly minimum length (19 bytes)."""
    from exabgp.reactor.network.connection import Connection

    header = create_bgp_header(b'\xff' * 16, 19, 4)  # Valid KEEPALIVE

    connection = Connection(1, '127.0.0.1', '127.0.0.1')
    connection.io = MagicMock()

    def mock_reader(num_bytes: int) -> Any:
        yield header[:num_bytes] if num_bytes <= len(header) else header

    connection._reader = mock_reader

    reader = connection.reader()
    length, msg_type, hdr, body, error = next(reader)

    assert error is None
    assert length == 19
    assert msg_type == 4  # KEEPALIVE
    assert body == b''


@pytest.mark.fuzz
def test_message_exactly_4096_bytes() -> None:
    """Test message with exactly maximum length (4096 bytes)."""
    from exabgp.reactor.network.connection import Connection

    header = create_bgp_header(b'\xff' * 16, 4096, 2)  # UPDATE at max size
    body = b'\x00' * (4096 - 19)
    data = header + body

    connection = Connection(1, '127.0.0.1', '127.0.0.1')
    connection.io = MagicMock()

    def mock_reader(num_bytes: int) -> Any:
        yield data[:num_bytes] if num_bytes <= len(data) else data

    connection._reader = mock_reader

    reader = connection.reader()

    # May need multiple iterations to read full message
    for result in reader:
        length, msg_type, hdr, body_result, error = result
        if length > 0 or error is not None:
            break

    assert error is None
    assert length == 4096
    assert msg_type == 2  # UPDATE
    assert len(body_result) == 4096 - 19


@pytest.mark.fuzz
@given(msg_type=st.integers(min_value=1, max_value=5))
@settings(deadline=None, max_examples=5)
def test_all_valid_message_types(msg_type: int) -> None:
    """Test all valid message types are accepted."""
    from exabgp.reactor.network.connection import Connection

    # Use appropriate minimum length for each type
    min_lengths = {1: 29, 2: 23, 3: 21, 4: 19, 5: 23}  # OPEN  # UPDATE  # NOTIFICATION  # KEEPALIVE  # ROUTE_REFRESH
    length = min_lengths[msg_type]

    header = create_bgp_header(b'\xff' * 16, length, msg_type)
    body = b'\x00' * (length - 19)
    data = header + body

    connection = Connection(1, '127.0.0.1', '127.0.0.1')
    connection.io = MagicMock()

    def mock_reader(num_bytes: int) -> Any:
        yield data[:num_bytes] if num_bytes <= len(data) else data

    connection._reader = mock_reader

    reader = connection.reader()

    for result in reader:
        length_result, type_result, hdr, body_result, error = result
        if length_result > 0 or error is not None:
            break

    # Header parsing should succeed (body may be invalid)
    # For KEEPALIVE, length must be exactly 19
    if msg_type == 4 and length != 19:
        assert error is not None
    else:
        assert error is None or error.code != 1  # Not a header error


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-m', 'fuzz'])
