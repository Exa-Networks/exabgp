"""Integration tests for Connection.reader_async(), the reader the daemon uses.

The bytes go through a socketpair (see tests/wire_reader.py), so the header checks
under test are the ones a peer's message actually meets.
"""

import pytest
from hypothesis import given, strategies as st, settings, HealthCheck
import struct

from exabgp.reactor.network.error import LostConnection, NotifyError
from tests.wire_reader import read_message

pytestmark = pytest.mark.fuzz


@pytest.mark.fuzz
@given(data=st.binary(min_size=0, max_size=100))
@settings(suppress_health_check=[HealthCheck.too_slow], deadline=None, max_examples=50)
def test_reader_with_random_data(data: bytes) -> None:
    """Test reader_async() with random binary data using actual implementation."""
    try:
        length, msg_type, header, body, error = read_message(data)
    except LostConnection:
        # The peer closed before sending the whole message
        return

    if error:
        assert isinstance(error, NotifyError)
    else:
        assert 19 <= length <= 4096
        assert msg_type == header[18]
        assert len(header) == 19
        assert len(body) == length - 19


@pytest.mark.fuzz
def test_reader_with_valid_keepalive() -> None:
    """Test reader_async() with a valid KEEPALIVE message."""
    # Valid KEEPALIVE: marker + length(19) + type(4)
    data = b'\xff' * 16 + struct.pack('!H', 19) + b'\x04'

    length, msg_type, header, body, error = read_message(data)

    assert error is None
    assert length == 19
    assert msg_type == 4
    assert header == data
    assert body == b''


@pytest.mark.fuzz
def test_reader_with_invalid_marker() -> None:
    """Test reader_async() rejects invalid marker."""
    # Invalid marker (all zeros instead of all 0xFF)
    data = b'\x00' * 16 + struct.pack('!H', 19) + b'\x01'

    length, msg_type, header, body, error = read_message(data)

    assert error is not None
    assert isinstance(error, NotifyError)
    assert error.code == 1  # Message Header Error
    assert error.subcode == 1  # Connection Not Synchronized


@pytest.mark.fuzz
def test_reader_with_invalid_length_too_small() -> None:
    """Test reader_async() rejects length < 19."""
    # Length = 18 (one below minimum)
    data = b'\xff' * 16 + struct.pack('!H', 18) + b'\x01'

    length, msg_type, header, body, error = read_message(data)

    assert error is not None
    assert isinstance(error, NotifyError)
    assert error.code == 1  # Message Header Error
    assert error.subcode == 2  # Bad Message Length
    # RFC 4271 6.1: the Data field carries the erroneous Length field
    assert error.data == struct.pack('!H', 18)


@pytest.mark.fuzz
def test_reader_with_invalid_length_too_large() -> None:
    """Test reader_async() rejects length > 4096 (default max)."""
    # Length = 4097 (one above standard maximum)
    data = b'\xff' * 16 + struct.pack('!H', 4097) + b'\x01'

    length, msg_type, header, body, error = read_message(data)

    assert error is not None
    assert isinstance(error, NotifyError)
    assert error.code == 1  # Message Header Error
    assert error.subcode == 2  # Bad Message Length
    assert error.data == struct.pack('!H', 4097)


@pytest.mark.fuzz
def test_reader_with_valid_open_message() -> None:
    """Test reader_async() with a valid OPEN message header."""
    # OPEN message with length 29
    header_data = b'\xff' * 16 + struct.pack('!H', 29) + b'\x01'
    body_data = b'\x00' * 10  # 10 bytes of body data (29 - 19)
    data = header_data + body_data

    length, msg_type, header, body, error = read_message(data)

    assert error is None
    assert length == 29
    assert msg_type == 1
    assert len(header) == 19
    assert len(body) == 10


@pytest.mark.fuzz
@given(length=st.integers(min_value=19, max_value=4096))
@settings(deadline=None, max_examples=50)
def test_reader_with_all_valid_lengths(length: int) -> None:
    """Fuzz reader_async() with all valid length values using KEEPALIVE."""
    body_size = length - 19
    header_data = b'\xff' * 16 + struct.pack('!H', length) + b'\x04'
    body_data = b'\x00' * body_size
    data = header_data + body_data

    result_length, msg_type, header, body, error = read_message(data)

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
        assert (error.code, error.subcode) == (1, 2)


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-m', 'fuzz'])
