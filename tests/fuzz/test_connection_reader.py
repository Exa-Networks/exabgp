"""Integration tests for connection.py::reader() function.

These tests exercise the actual reader() implementation by mocking
the underlying _reader() generator to provide test data.
"""
import pytest
from typing import Any
from unittest.mock import Mock, MagicMock
from hypothesis import given, strategies as st, settings, HealthCheck
import struct

pytestmark = pytest.mark.fuzz


def create_mock_connection_with_data(data: bytes) -> Any:
    """Create a mock Connection object that will yield the given data.

    Args:
        data: Bytes to be returned by the mocked _reader()

    Returns:
        Mock connection object with reader() method ready to use
    """
    from exabgp.reactor.network.connection import Connection

    # Create a real Connection instance
    connection = Connection(1, '127.0.0.1', '127.0.0.1')
    connection.io = MagicMock()  # Mock the socket

    # Mock _reader to return our test data in chunks
    def mock_reader(num_bytes: int) -> Any:
        """Generator that yields data in chunks.

        Mimics the behavior of the real _reader() which yields empty bytes
        when waiting for data, and eventually yields the requested data.
        """
        if len(data) < num_bytes:
            # Not enough data - yield empty bytes to signal waiting
            yield b''
            return
        # Yield the exact number of bytes requested
        yield data[:num_bytes]

    connection._reader = mock_reader
    return connection


@pytest.mark.fuzz
@given(data=st.binary(min_size=0, max_size=100))
@settings(suppress_health_check=[HealthCheck.too_slow], deadline=None, max_examples=50)
def test_reader_with_random_data(data: bytes) -> None:
    """Test reader() with random binary data using actual implementation."""
    from exabgp.reactor.network.error import NotifyError

    connection = create_mock_connection_with_data(data)

    try:
        reader = connection.reader()
        result = next(reader)

        # reader() yields tuples with (length, msg_type, header, body, error)
        # During reading, it may yield (0, 0, b'', b'', None) when waiting for data
        # Keep consuming until we get a final result or the generator stops
        while result == (0, 0, b'', b'', None):
            result = next(reader)

        length, msg_type, header, body, error = result

        if error:
            # Should be a NotifyError for invalid data
            assert isinstance(error, NotifyError)
        elif length > 0:
            # Valid parse - verify the data
            assert 19 <= length <= 4096
            assert 1 <= msg_type <= 5 or msg_type == 0  # Allow NOP for valid length=0
            assert len(header) == 19
    except StopIteration:
        # Generator exhausted - expected for insufficient data
        pass


@pytest.mark.fuzz
def test_reader_with_valid_keepalive() -> None:
    """Test reader() with a valid KEEPALIVE message."""
    # Valid KEEPALIVE: marker + length(19) + type(4)
    data = b'\xFF' * 16 + struct.pack('!H', 19) + b'\x04'

    connection = create_mock_connection_with_data(data)
    reader = connection.reader()

    length, msg_type, header, body, error = next(reader)

    assert error is None
    assert length == 19
    assert msg_type == 4
    assert header == data
    assert body == b''


@pytest.mark.fuzz
def test_reader_with_invalid_marker() -> None:
    """Test reader() rejects invalid marker."""
    from exabgp.reactor.network.error import NotifyError

    # Invalid marker (all zeros instead of all 0xFF)
    data = b'\x00' * 16 + struct.pack('!H', 19) + b'\x01'

    connection = create_mock_connection_with_data(data)
    reader = connection.reader()

    length, msg_type, header, body, error = next(reader)

    assert error is not None
    assert isinstance(error, NotifyError)
    assert error.code == 1  # Message Header Error
    assert error.subcode == 1  # Connection Not Synchronized


@pytest.mark.fuzz
def test_reader_with_invalid_length_too_small() -> None:
    """Test reader() rejects length < 19."""
    from exabgp.reactor.network.error import NotifyError

    # Length = 18 (one below minimum)
    data = b'\xFF' * 16 + struct.pack('!H', 18) + b'\x01'

    connection = create_mock_connection_with_data(data)
    reader = connection.reader()

    length, msg_type, header, body, error = next(reader)

    assert error is not None
    assert isinstance(error, NotifyError)
    assert error.code == 1  # Message Header Error
    assert error.subcode == 2  # Bad Message Length


@pytest.mark.fuzz
def test_reader_with_invalid_length_too_large() -> None:
    """Test reader() rejects length > 4096 (default max)."""
    from exabgp.reactor.network.error import NotifyError

    # Length = 4097 (one above standard maximum)
    data = b'\xFF' * 16 + struct.pack('!H', 4097) + b'\x01'

    connection = create_mock_connection_with_data(data)
    reader = connection.reader()

    length, msg_type, header, body, error = next(reader)

    assert error is not None
    assert isinstance(error, NotifyError)
    assert error.code == 1  # Message Header Error
    assert error.subcode == 2  # Bad Message Length


@pytest.mark.fuzz
def test_reader_with_valid_open_message() -> None:
    """Test reader() with a valid OPEN message header."""
    # OPEN message with length 29
    header_data = b'\xFF' * 16 + struct.pack('!H', 29) + b'\x01'
    body_data = b'\x00' * 10  # 10 bytes of body data (29 - 19)
    data = header_data + body_data

    connection = create_mock_connection_with_data(data)
    reader = connection.reader()

    length, msg_type, header, body, error = next(reader)

    assert error is None
    assert length == 29
    assert msg_type == 1
    assert len(header) == 19
    assert len(body) == 10


@pytest.mark.fuzz
@given(length=st.integers(min_value=19, max_value=4096))
@settings(deadline=None, max_examples=50)
def test_reader_with_all_valid_lengths(length: int) -> None:
    """Fuzz reader() with all valid length values using KEEPALIVE (most permissive)."""
    from exabgp.reactor.network.error import NotifyError

    body_size = length - 19
    # Use KEEPALIVE (type 4) which accepts length >= 19
    header_data = b'\xFF' * 16 + struct.pack('!H', length) + b'\x04'
    body_data = b'\x00' * body_size
    data = header_data + body_data

    connection = create_mock_connection_with_data(data)
    reader = connection.reader()

    # Consume any intermediate yields
    for result in reader:
        result_length, msg_type, header, body, error = result
        if result_length > 0 or error is not None:
            break

    # KEEPALIVE should only be exactly 19 bytes
    if length == 19:
        assert error is None
        assert result_length == length
        assert msg_type == 4
        assert len(body) == body_size
    else:
        # Length > 19 for KEEPALIVE is invalid
        assert error is not None
        assert isinstance(error, NotifyError)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "fuzz"])
