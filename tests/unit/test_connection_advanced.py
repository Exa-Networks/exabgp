#!/usr/bin/env python3
# encoding: utf-8
"""test_connection_advanced.py

Advanced tests for network connection layer functionality.
Tests generator-based I/O, BGP message validation, multi-packet assembly, and buffer management.

Created: 2025-11-08
"""

import asyncio
import pytest
import os
import socket
import struct
from unittest.mock import Mock, patch

# Set up environment before importing ExaBGP modules
os.environ['exabgp_log_enable'] = 'false'
os.environ['exabgp_log_level'] = 'CRITICAL'

from exabgp.protocol.family import AFI
from exabgp.reactor.network.connection import Connection
from exabgp.reactor.network.error import (
    NotConnected,
    LostConnection,
    TooSlowError,
    NetworkError,
    NotifyError,
    errno,
)
from exabgp.bgp.message import Message
from tests.wire_reader import loopback_connection, read_message, read_messages

# Long enough that the read is certainly waiting on the event loop when the data arrives.
DELIVERY_DELAY_SECONDS = 0.05


class TestSocketReader:
    """Test _reader_async(), which reads an exact number of bytes off the socket"""

    def test_reader_no_socket_raises_not_connected(self) -> None:
        """Test _reader_async() raises NotConnected when no socket"""
        conn = Connection(AFI.ipv4, '192.0.2.1', '192.0.2.2')

        with pytest.raises(NotConnected) as exc_info:
            asyncio.run(conn._reader_async(10))

        assert 'closed TCP connection' in str(exc_info.value)

    def test_reader_zero_bytes_returns_empty(self) -> None:
        """Test _reader_async(0) returns an empty memoryview immediately"""
        conn = Connection(AFI.ipv4, '192.0.2.1', '192.0.2.2')
        conn.io = Mock()

        result = asyncio.run(conn._reader_async(0))

        assert result == b''
        # Should not call recv_into for zero bytes
        conn.io.recv_into.assert_not_called()

    def test_reader_waits_for_socket_ready(self) -> None:
        """Test _reader_async() waits on the event loop until data arrives"""
        ours, theirs = socket.socketpair()
        conn = loopback_connection(ours)

        async def read_after_delay() -> memoryview:
            # Nothing is buffered when the read starts: the first recv_into would block
            asyncio.get_running_loop().call_later(DELIVERY_DELAY_SECONDS, theirs.send, b'test')
            return await conn._reader_async(4)

        try:
            with patch('exabgp.reactor.network.connection.log'):
                result = asyncio.run(read_after_delay())
            assert result == b'test'
            assert conn._read_buffer is None
        finally:
            conn.close()
            theirs.close()

    def test_reader_assembles_partial_reads(self) -> None:
        """Test _reader_async() assembles data from multiple recv_into() calls"""
        conn = Connection(AFI.ipv4, '192.0.2.1', '192.0.2.2')

        mock_sock = Mock()
        mock_sock.fileno.return_value = 5
        conn.io = mock_sock

        # Simulate partial reads: request 10 bytes, get 4, then 6
        chunks = [b'test', b'data12']
        chunk_iter = iter(chunks)

        def recv_into_side_effect(buffer: memoryview) -> int:
            """Mock recv_into: writes data to buffer and returns bytes written"""
            data = next(chunk_iter)
            buffer[: len(data)] = data
            return len(data)

        mock_sock.recv_into.side_effect = recv_into_side_effect

        with patch('exabgp.reactor.network.connection.log'):
            result = asyncio.run(conn._reader_async(10))

        assert result == b'testdata12'
        assert mock_sock.recv_into.call_count == 2

    def test_reader_handles_blocking_error(self) -> None:
        """Test _reader_async() waits through EAGAIN and keeps what it already read"""
        ours, theirs = socket.socketpair()
        conn = loopback_connection(ours)

        async def read_in_two_parts() -> memoryview:
            # The first half is buffered; the second arrives after recv_into saw EAGAIN
            theirs.send(b'da')
            asyncio.get_running_loop().call_later(DELIVERY_DELAY_SECONDS, theirs.send, b'ta')
            return await conn._reader_async(4)

        try:
            with patch('exabgp.reactor.network.connection.log'):
                result = asyncio.run(read_in_two_parts())
            assert result == b'data'
        finally:
            conn.close()
            theirs.close()

    def test_reader_raises_lost_connection_on_empty_recv(self) -> None:
        """Test _reader_async() raises LostConnection when recv_into returns 0"""
        conn = Connection(AFI.ipv4, '192.0.2.1', '192.0.2.2')

        mock_sock = Mock()
        mock_sock.fileno.return_value = 5
        conn.io = mock_sock
        mock_sock.recv_into.return_value = 0  # Connection closed (recv_into returns 0)

        with patch('exabgp.reactor.network.connection.log'):
            with pytest.raises(LostConnection) as exc_info:
                asyncio.run(conn._reader_async(10))

        assert 'closed by the remote end' in str(exc_info.value)
        # The connection is closed, and the half read message forgotten with it
        assert conn.io is None
        assert conn._read_buffer is None

    def test_reader_raises_too_slow_on_timeout(self) -> None:
        """Test _reader_async() raises TooSlowError on socket timeout"""
        conn = Connection(AFI.ipv4, '192.0.2.1', '192.0.2.2')

        mock_sock = Mock()
        mock_sock.fileno.return_value = 5
        conn.io = mock_sock
        mock_sock.recv_into.side_effect = socket.timeout('timed out')

        with patch('exabgp.reactor.network.connection.log'):
            with pytest.raises(TooSlowError) as exc_info:
                asyncio.run(conn._reader_async(10))

        assert 'Timeout' in str(exc_info.value)
        # The connection is closed, and the half read message forgotten with it
        assert conn.io is None
        assert conn._read_buffer is None

    def test_reader_raises_lost_connection_on_fatal_error(self) -> None:
        """Test _reader_async() raises LostConnection on fatal socket errors"""
        conn = Connection(AFI.ipv4, '192.0.2.1', '192.0.2.2')

        mock_sock = Mock()
        mock_sock.fileno.return_value = 5
        conn.io = mock_sock
        mock_sock.recv_into.side_effect = OSError(errno.ECONNRESET, 'Connection reset')

        with patch('exabgp.reactor.network.connection.log'):
            with pytest.raises(LostConnection) as exc_info:
                asyncio.run(conn._reader_async(10))

        assert 'issue reading on the socket' in str(exc_info.value)
        # The connection is closed, and the half read message forgotten with it
        assert conn.io is None
        assert conn._read_buffer is None


class TestGeneratorBasedWriter:
    """Test writer() generator-based I/O method"""

    def test_writer_no_socket_yields_true(self) -> None:
        """Test writer() yields True immediately when no socket"""
        conn = Connection(AFI.ipv4, '192.0.2.1', '192.0.2.2')

        gen = conn.writer(b'test')
        result = next(gen)

        assert result is True

    def test_writer_waits_for_socket_ready(self) -> None:
        """Test writer() yields False while waiting for socket ready"""
        conn = Connection(AFI.ipv4, '192.0.2.1', '192.0.2.2')

        mock_sock = Mock()
        mock_sock.fileno.return_value = 5
        conn.io = mock_sock

        # Create a mock poller that returns not ready first, then ready
        poll_results = [[], [(5, 4)]]  # First not ready, then POLLOUT

        with patch('select.poll') as mock_poll:
            mock_poller = Mock()
            mock_poller.poll.side_effect = poll_results
            mock_poll.return_value = mock_poller

            mock_sock.send.return_value = 4

            with patch('exabgp.reactor.network.connection.log'):
                gen = conn.writer(b'test')

                # First yield should be False (waiting)
                result = next(gen)
                assert result is False

                # Second yield should be True (sent)
                result = next(gen)
                assert result is True

    def test_writer_partial_sends(self) -> None:
        """Test writer() handles partial send() results"""
        conn = Connection(AFI.ipv4, '192.0.2.1', '192.0.2.2')

        mock_sock = Mock()
        mock_sock.fileno.return_value = 5
        conn.io = mock_sock

        # Simulate partial sends: send 4 bytes, then 6 bytes
        send_results = [4, 6]
        mock_sock.send.side_effect = send_results

        with patch('select.poll') as mock_poll:
            mock_poller = Mock()
            mock_poller.poll.return_value = [(5, 4)]  # Always ready
            mock_poll.return_value = mock_poller

            with patch('exabgp.reactor.network.connection.log'):
                gen = conn.writer(b'testdata12')

                results = []
                for result in gen:
                    results.append(result)

                # Should yield False after first partial send, True when complete
                assert False in results
                assert results[-1] is True
                assert mock_sock.send.call_count == 2

    def test_writer_handles_blocking_error(self) -> None:
        """Test writer() handles EAGAIN/EWOULDBLOCK errors"""
        conn = Connection(AFI.ipv4, '192.0.2.1', '192.0.2.2')

        mock_sock = Mock()
        mock_sock.fileno.return_value = 5
        conn.io = mock_sock

        # First call raises EAGAIN, second succeeds
        mock_sock.send.side_effect = [
            OSError(errno.EAGAIN, 'Would block'),
            4,
        ]

        with patch('select.poll') as mock_poll:
            mock_poller = Mock()
            mock_poller.poll.return_value = [(5, 4)]  # Always ready
            mock_poll.return_value = mock_poller

            with patch('exabgp.reactor.network.connection.log'):
                with patch('exabgp.reactor.network.connection.log'):
                    gen = conn.writer(b'test')

                    results = []
                    for result in gen:
                        results.append(result)

                    # Should yield False on EAGAIN, then True
                    assert False in results
                    assert results[-1] is True

    def test_writer_raises_network_error_on_epipe(self) -> None:
        """Test writer() raises NetworkError on EPIPE (broken pipe)"""
        conn = Connection(AFI.ipv4, '192.0.2.1', '192.0.2.2')

        mock_sock = Mock()
        mock_sock.fileno.return_value = 5
        conn.io = mock_sock

        error = OSError(errno.EPIPE, 'Broken pipe')
        error.errno = errno.EPIPE
        mock_sock.send.side_effect = error

        with patch('select.poll') as mock_poll:
            mock_poller = Mock()
            mock_poller.poll.return_value = [(5, 4)]
            mock_poll.return_value = mock_poller

            with patch('exabgp.reactor.network.connection.log'):
                gen = conn.writer(b'test')

                with pytest.raises(NetworkError) as exc_info:
                    for _ in gen:
                        pass

                assert 'Broken TCP connection' in str(exc_info.value)

    def test_writer_raises_lost_connection_on_zero_send(self) -> None:
        """Test writer() raises LostConnection when send returns 0"""
        conn = Connection(AFI.ipv4, '192.0.2.1', '192.0.2.2')

        mock_sock = Mock()
        mock_sock.fileno.return_value = 5
        conn.io = mock_sock
        mock_sock.send.return_value = 0  # Connection lost

        with patch('select.poll') as mock_poll:
            mock_poller = Mock()
            mock_poller.poll.return_value = [(5, 4)]
            mock_poll.return_value = mock_poller

            with patch('exabgp.reactor.network.connection.log'):
                with patch('exabgp.reactor.network.connection.log'):
                    gen = conn.writer(b'test')

                    with pytest.raises(LostConnection):
                        for _ in gen:
                            pass


class TestBGPHeaderValidation:
    """Test BGP message header validation with error conditions"""

    def test_reader_validates_marker(self) -> None:
        """Test reader_async() validates BGP marker field"""
        # Invalid marker (all zeros instead of all 0xFF)
        header_data = b'\x00' * 16 + struct.pack('!H', 19) + b'\x04'

        length, msg_type, header, body, error = read_message(header_data)

        assert error is not None
        assert isinstance(error, NotifyError)
        assert error.code == 1  # Message Header Error
        assert error.subcode == 1  # Connection Not Synchronized

    def test_reader_validates_length_minimum(self) -> None:
        """Test reader_async() rejects length < 19"""
        # Length = 18 (below minimum)
        header_data = Message.MARKER + struct.pack('!H', 18) + b'\x01'

        length, msg_type, header, body, error = read_message(header_data)

        assert error is not None
        assert isinstance(error, NotifyError)
        assert error.code == 1  # Message Header Error
        assert error.subcode == 2  # Bad Message Length
        # RFC 4271 6.1: the Data field "MUST contain the erroneous Length field"
        assert error.data == struct.pack('!H', 18)

    def test_reader_validates_length_maximum(self) -> None:
        """Test reader_async() rejects length > msg_size"""
        # Length = 4097 (above default maximum of 4096)
        header_data = Message.MARKER + struct.pack('!H', 4097) + b'\x01'

        length, msg_type, header, body, error = read_message(header_data)

        assert error is not None
        assert isinstance(error, NotifyError)
        assert error.code == 1  # Message Header Error
        assert error.subcode == 2  # Bad Message Length
        # RFC 4271 6.1: the Data field "MUST contain the erroneous Length field"
        assert error.data == struct.pack('!H', 4097)

    def test_reader_validates_keepalive_length(self) -> None:
        """Test reader_async() validates KEEPALIVE must be exactly 19 bytes"""
        # KEEPALIVE with length 20 (should be exactly 19)
        header_data = Message.MARKER + struct.pack('!H', 20) + b'\x04' + b'\x00'

        length, msg_type, header, body, error = read_message(header_data)

        assert error is not None
        assert isinstance(error, NotifyError)
        assert error.code == 1  # Message Header Error
        assert error.subcode == 2  # Bad Message Length
        # RFC 4271 6.1: the Data field "MUST contain the erroneous Length field"
        assert error.data == struct.pack('!H', 20)

    def test_reader_validates_open_minimum_length(self) -> None:
        """Test reader_async() validates OPEN must be >= 29 bytes"""
        # OPEN with length 28 (below minimum of 29)
        header_data = Message.MARKER + struct.pack('!H', 28) + b'\x01' + b'\x00' * 9

        length, msg_type, header, body, error = read_message(header_data)

        assert error is not None
        assert isinstance(error, NotifyError)
        assert error.code == 1  # Message Header Error
        assert error.subcode == 2  # Bad Message Length
        # RFC 4271 6.1: the Data field "MUST contain the erroneous Length field"
        assert error.data == struct.pack('!H', 28)

    def test_reader_validates_update_minimum_length(self) -> None:
        """Test reader_async() validates UPDATE must be >= 23 bytes"""
        # UPDATE with length 22 (below minimum of 23)
        header_data = Message.MARKER + struct.pack('!H', 22) + b'\x02' + b'\x00' * 3

        length, msg_type, header, body, error = read_message(header_data)

        assert error is not None
        assert isinstance(error, NotifyError)
        assert error.code == 1  # Message Header Error
        assert error.subcode == 2  # Bad Message Length
        # RFC 4271 6.1: the Data field "MUST contain the erroneous Length field"
        assert error.data == struct.pack('!H', 22)

    def test_reader_accepts_valid_keepalive(self) -> None:
        """Test reader_async() accepts valid KEEPALIVE message"""
        # Valid KEEPALIVE: marker + length(19) + type(4)
        header_data = Message.MARKER + struct.pack('!H', 19) + b'\x04'

        length, msg_type, header, body, error = read_message(header_data)

        assert error is None
        assert length == 19
        assert msg_type == 4
        assert header == header_data
        assert body == b''


class TestMultiPacketAssembly:
    """Test multi-packet message assembly"""

    def test_reader_assembles_message_with_body(self) -> None:
        """Test reader_async() assembles header and body into complete message"""
        header_data = Message.MARKER + struct.pack('!H', 29) + bytes([1])
        body_data = b'\x04\xac\x10\x00\x01\x00\xb4\xc0\xa8\x01'  # 10 bytes

        length, msg_type, header, body, error = read_message(header_data + body_data)

        assert error is None
        assert length == 29
        assert msg_type == 1
        assert header == header_data
        assert body == body_data

    def test_reader_handles_large_update_message(self) -> None:
        """Test reader_async() handles large UPDATE messages"""
        header_data = Message.MARKER + struct.pack('!H', 1000) + bytes([2])
        body_data = b'\x00' * (1000 - 19)

        length, msg_type, header, body, error = read_message(header_data + body_data)

        assert error is None
        assert length == 1000
        assert msg_type == 2
        assert header == header_data
        assert body == body_data

    def test_reader_waits_between_header_and_body(self) -> None:
        """Test reader_async() waits for a body which arrives after its header"""
        ours, theirs = socket.socketpair()
        conn = loopback_connection(ours)
        header_data = Message.MARKER + struct.pack('!H', 29) + b'\x01'
        body_data = b'\x00' * 10

        async def read_split_message() -> tuple:
            theirs.send(header_data)
            asyncio.get_running_loop().call_later(DELIVERY_DELAY_SECONDS, theirs.send, body_data)
            return await conn.reader_async()

        try:
            with patch('exabgp.reactor.network.connection.log'):
                length, msg_type, header, body, error = asyncio.run(read_split_message())
            assert error is None
            assert length == 29
            assert body == body_data
            assert conn._read_header is None
        finally:
            conn.close()
            theirs.close()


class TestBufferManagement:
    """Test buffer management scenarios"""

    def test_reader_handles_incremental_header_reads(self) -> None:
        """Test _reader_async() assembles header from small incremental reads"""
        conn = Connection(AFI.ipv4, '192.0.2.1', '192.0.2.2')

        mock_sock = Mock()
        mock_sock.fileno.return_value = 5
        conn.io = mock_sock

        # Simulate receiving header in 1-byte chunks
        header_bytes = Message.MARKER + struct.pack('!H', 19) + b'\x04'
        chunks = [bytes([b]) for b in header_bytes]
        chunk_iter = iter(chunks)

        def recv_into_side_effect(buffer: memoryview) -> int:
            data = next(chunk_iter)
            buffer[: len(data)] = data
            return len(data)

        mock_sock.recv_into.side_effect = recv_into_side_effect

        with patch('exabgp.reactor.network.connection.log'):
            result = asyncio.run(conn._reader_async(19))

        assert result == header_bytes
        assert mock_sock.recv_into.call_count == 19

    def test_reader_handles_variable_chunk_sizes(self) -> None:
        """Test _reader_async() handles variable-size recv_into() chunks"""
        conn = Connection(AFI.ipv4, '192.0.2.1', '192.0.2.2')

        mock_sock = Mock()
        mock_sock.fileno.return_value = 5
        conn.io = mock_sock

        # Simulate variable chunk sizes: 5, 3, 7, 4, 1 bytes (total 20)
        chunks = [
            b'12345',
            b'678',
            b'abcdefg',
            b'hijk',
            b'l',
        ]
        chunk_iter = iter(chunks)

        def recv_into_side_effect(buffer: memoryview) -> int:
            data = next(chunk_iter)
            buffer[: len(data)] = data
            return len(data)

        mock_sock.recv_into.side_effect = recv_into_side_effect

        with patch('exabgp.reactor.network.connection.log'):
            result = asyncio.run(conn._reader_async(20))

        assert result == b'12345678abcdefghijkl'
        assert mock_sock.recv_into.call_count == 5

    def test_writer_handles_incremental_sends(self) -> None:
        """Test writer() handles incremental send() results"""
        conn = Connection(AFI.ipv4, '192.0.2.1', '192.0.2.2')

        mock_sock = Mock()
        mock_sock.fileno.return_value = 5
        conn.io = mock_sock

        # Simulate sending in 5-byte chunks
        data = b'0123456789abcdefghij'  # 20 bytes
        send_results = [5, 5, 5, 5]  # 4 sends of 5 bytes each
        mock_sock.send.side_effect = send_results

        with patch('select.poll') as mock_poll:
            mock_poller = Mock()
            mock_poller.poll.return_value = [(5, 4)]  # Always ready
            mock_poll.return_value = mock_poller

            with patch('exabgp.reactor.network.connection.log'):
                gen = conn.writer(data)

                results = []
                for result in gen:
                    results.append(result)

                # Should eventually yield True
                assert results[-1] is True
                assert mock_sock.send.call_count == 4

    def test_reader_buffer_boundary_conditions(self) -> None:
        """Test _reader_async() handles exact buffer boundaries"""
        conn = Connection(AFI.ipv4, '192.0.2.1', '192.0.2.2')

        mock_sock = Mock()
        mock_sock.fileno.return_value = 5
        conn.io = mock_sock

        # Request exactly what's available
        data = b'exactly100bytes' * 6 + b'exactly10b'  # 100 bytes

        def recv_into_side_effect(buffer: memoryview) -> int:
            buffer[: len(data)] = data
            return len(data)

        mock_sock.recv_into.side_effect = recv_into_side_effect

        with patch('exabgp.reactor.network.connection.log'):
            result = asyncio.run(conn._reader_async(100))

        assert result == data
        assert len(result) == 100

    def test_reader_empty_body_message(self) -> None:
        """Test reader_async() handles message with no body (header only)"""
        # KEEPALIVE has no body, just header
        header_data = Message.MARKER + struct.pack('!H', 19) + b'\x04'

        length, msg_type, header, body, error = read_message(header_data)

        assert error is None
        assert length == 19
        assert msg_type == 4
        assert body == b''  # No body for KEEPALIVE


class TestPollingMechanisms:
    """Test the writing() polling mechanism used by writer()"""

    def test_writing_registers_poller_once(self) -> None:
        """Test writing() registers poller only once"""
        conn = Connection(AFI.ipv4, '192.0.2.1', '192.0.2.2')

        mock_sock = Mock()
        mock_sock.fileno.return_value = 5
        conn.io = mock_sock

        with patch('select.poll') as mock_poll:
            mock_poller = Mock()
            mock_poller.poll.return_value = [(5, 4)]
            mock_poll.return_value = mock_poller

            # First call should register
            conn.writing()
            assert mock_poll.call_count == 1
            assert mock_poller.register.call_count == 1

            # Second call should reuse poller
            conn.writing()
            assert mock_poll.call_count == 1
            assert mock_poller.register.call_count == 1

    def test_writing_detects_error(self) -> None:
        """Test writing() detects POLLERR event"""
        conn = Connection(AFI.ipv4, '192.0.2.1', '192.0.2.2')

        mock_sock = Mock()
        mock_sock.fileno.return_value = 5
        conn.io = mock_sock

        with patch('select.poll') as mock_poll:
            import select

            mock_poller = Mock()
            mock_poller.poll.return_value = [(5, select.POLLERR)]
            mock_poll.return_value = mock_poller

            result = conn.writing()

            assert result is True
            # Poller should be cleared on error
            assert conn._wpoller == {}

    def test_writing_returns_false_when_no_socket(self) -> None:
        """Test writing() returns False when io is None"""
        conn = Connection(AFI.ipv4, '192.0.2.1', '192.0.2.2')
        conn.io = None

        result = conn.writing()

        assert result is False


class TestConnectionBasics:
    """Test basic Connection initialization and utility methods"""

    def test_init_ipv4_connection(self) -> None:
        """Test Connection initialization with IPv4"""
        conn = Connection(AFI.ipv4, '192.0.2.1', '192.0.2.2')

        assert conn.afi == AFI.ipv4
        assert conn.peer == '192.0.2.1'
        assert conn.local == '192.0.2.2'
        assert conn.io is None
        assert conn.established is False
        assert conn.msg_size == 4096  # INITIAL_SIZE
        assert conn._wpoller == {}

    def test_init_ipv6_connection(self) -> None:
        """Test Connection initialization with IPv6"""
        from exabgp.protocol.family import AFI

        conn = Connection(AFI.ipv6, '2001:db8::1', '2001:db8::2')

        assert conn.afi == AFI.ipv6
        assert conn.peer == '2001:db8::1'
        assert conn.local == '2001:db8::2'

    def test_name_returns_formatted_string(self) -> None:
        """Test name() returns properly formatted connection name"""
        conn = Connection(AFI.ipv4, '192.0.2.1', '192.0.2.2')
        conn.direction = 'outgoing'
        conn.id = 5

        name = conn.name()

        assert 'outgoing-5' in name
        assert '192.0.2.2-192.0.2.1' in name

    def test_session_returns_direction_and_id(self) -> None:
        """Test session() returns session identifier"""
        conn = Connection(AFI.ipv4, '192.0.2.1', '192.0.2.2')
        conn.direction = 'incoming'
        conn.id = 3

        session = conn.session()

        assert session == 'incoming-3'

    def test_fd_returns_fileno_when_socket_exists(self) -> None:
        """Test fd() returns file descriptor when socket exists"""
        conn = Connection(AFI.ipv4, '192.0.2.1', '192.0.2.2')

        mock_sock = Mock()
        mock_sock.fileno.return_value = 42
        conn.io = mock_sock

        fd = conn.fd()

        assert fd == 42
        mock_sock.fileno.assert_called_once()

    def test_fd_returns_minus_one_when_no_socket(self) -> None:
        """Test fd() returns -1 when no socket"""
        conn = Connection(AFI.ipv4, '192.0.2.1', '192.0.2.2')

        fd = conn.fd()

        assert fd == -1

    def test_success_increments_identifier(self) -> None:
        """Test success() increments connection identifier"""
        conn = Connection(AFI.ipv4, '192.0.2.1', '192.0.2.2')
        conn.direction = 'outgoing'
        conn.identifier = {'outgoing': 5}

        new_id = conn.success()

        assert new_id == 6
        assert conn.identifier['outgoing'] == 6

    def test_success_initializes_identifier(self) -> None:
        """Test success() initializes identifier if not present"""
        conn = Connection(AFI.ipv4, '192.0.2.1', '192.0.2.2')
        conn.direction = 'incoming'
        conn.identifier = {}

        new_id = conn.success()

        assert new_id == 2  # 1 + 1
        assert conn.identifier['incoming'] == 2

    def test_close_with_active_socket(self) -> None:
        """Test close() properly closes active socket"""
        conn = Connection(AFI.ipv4, '192.0.2.1', '192.0.2.2')

        mock_sock = Mock()
        conn.io = mock_sock

        with patch('exabgp.reactor.network.connection.log'):
            conn.close()

        mock_sock.close.assert_called_once()
        assert conn.io is None

    def test_close_with_no_socket(self) -> None:
        """Test close() handles case when no socket exists"""
        conn = Connection(AFI.ipv4, '192.0.2.1', '192.0.2.2')
        conn.io = None

        with patch('exabgp.reactor.network.connection.log'):
            # Should not raise exception
            conn.close()

        assert conn.io is None

    def test_close_handles_socket_error(self) -> None:
        """Test close() handles socket errors gracefully"""
        conn = Connection(AFI.ipv4, '192.0.2.1', '192.0.2.2')

        mock_sock = Mock()
        mock_sock.close.side_effect = OSError('Socket already closed')
        conn.io = mock_sock

        with patch('exabgp.reactor.network.connection.log'):
            # Should not raise exception
            conn.close()

        assert conn.io is None


class TestExtendedMessageSize:
    """Test message size handling including extended messages"""

    def test_default_message_size(self) -> None:
        """Test default message size is 4096 bytes"""
        conn = Connection(AFI.ipv4, '192.0.2.1', '192.0.2.2')

        assert conn.msg_size == 4096

    def test_extended_message_size_change(self) -> None:
        """Test message size can be changed for extended messages"""
        conn = Connection(AFI.ipv4, '192.0.2.1', '192.0.2.2')

        # Simulate negotiating extended message capability
        conn.msg_size = 65535

        assert conn.msg_size == 65535

    def test_reader_validates_against_current_msg_size(self) -> None:
        """Test reader_async() validates length against current msg_size"""
        # Message with length 101 (exceeds msg_size)
        header_data = Message.MARKER + struct.pack('!H', 101) + b'\x02'

        length, msg_type, header, body, error = read_message(header_data, msg_size=100)

        assert error is not None
        assert isinstance(error, NotifyError)
        assert error.code == 1  # Message Header Error
        assert error.subcode == 2  # Bad Message Length
        # RFC 4271 6.1: the Data field "MUST contain the erroneous Length field"
        assert error.data == struct.pack('!H', 101)

    def test_reader_accepts_extended_size_when_configured(self) -> None:
        """Test reader_async() accepts large messages when extended size configured"""
        header_data = Message.MARKER + struct.pack('!H', 5000) + bytes([2])
        body_data = b'\x00' * (5000 - 19)

        length, msg_type, header, body, error = read_message(header_data + body_data, msg_size=65535)

        assert error is None
        assert length == 5000
        assert msg_type == 2
        assert header == header_data
        assert body == body_data


class TestErrorPropagation:
    """Test error propagation through Connection methods"""

    def test_writer_propagates_fatal_error(self) -> None:
        """Test writer() propagates fatal socket errors"""
        conn = Connection(AFI.ipv4, '192.0.2.1', '192.0.2.2')

        mock_sock = Mock()
        mock_sock.fileno.return_value = 5
        conn.io = mock_sock

        error = OSError(errno.ECONNRESET, 'Connection reset')
        error.errno = errno.ECONNRESET
        mock_sock.send.side_effect = error

        with patch('select.poll') as mock_poll:
            mock_poller = Mock()
            mock_poller.poll.return_value = [(5, 4)]
            mock_poll.return_value = mock_poller

            with patch('exabgp.reactor.network.connection.log'):
                with patch('exabgp.reactor.network.connection.log'):
                    gen = conn.writer(b'test')

                    with pytest.raises(NetworkError) as exc_info:
                        for _ in gen:
                            pass

                    assert 'Problem while writing data' in str(exc_info.value)

    def test_reader_propagates_fatal_error(self) -> None:
        """Test _reader_async() propagates fatal socket errors"""
        conn = Connection(AFI.ipv4, '192.0.2.1', '192.0.2.2')

        mock_sock = Mock()
        mock_sock.fileno.return_value = 5
        conn.io = mock_sock
        mock_sock.recv_into.side_effect = OSError(errno.ECONNREFUSED, 'Connection refused')

        with patch('exabgp.reactor.network.connection.log'):
            with pytest.raises(LostConnection) as exc_info:
                asyncio.run(conn._reader_async(10))

        assert 'issue reading on the socket' in str(exc_info.value)
        # Socket should be closed
        assert conn.io is None

    def test_reader_clears_socket_on_error(self) -> None:
        """Test _reader_async() clears socket on connection loss"""
        conn = Connection(AFI.ipv4, '192.0.2.1', '192.0.2.2')

        mock_sock = Mock()
        mock_sock.fileno.return_value = 5
        conn.io = mock_sock
        mock_sock.recv_into.return_value = 0  # Connection closed (recv_into returns 0)

        with patch('exabgp.reactor.network.connection.log'):
            with pytest.raises(LostConnection) as exc_info:
                asyncio.run(conn._reader_async(10))

        assert 'closed by the remote end' in str(exc_info.value)
        # Socket should be closed
        assert conn.io is None


class TestNotificationErrorTypes:
    """Test different BGP NOTIFICATION error codes"""

    def test_reader_connection_not_synchronized_error(self) -> None:
        """Test reader_async() generates connection not synchronized error"""
        # Invalid marker
        header_data = b'\x00' * 16 + struct.pack('!H', 19) + b'\x04'

        length, msg_type, header, body, error = read_message(header_data)

        assert error is not None
        assert isinstance(error, NotifyError)
        assert error.code == 1  # Message Header Error
        assert error.subcode == 1  # Connection Not Synchronized

    def test_reader_bad_message_length_too_small(self) -> None:
        """Test reader_async() generates bad message length error for too small"""
        # Length 10 (below minimum 19)
        header_data = Message.MARKER + struct.pack('!H', 10) + b'\x01'

        length, msg_type, header, body, error = read_message(header_data)

        assert error is not None
        assert isinstance(error, NotifyError)
        assert error.code == 1  # Message Header Error
        assert error.subcode == 2  # Bad Message Length
        # RFC 4271 6.1: the Data field "MUST contain the erroneous Length field"
        assert error.data == struct.pack('!H', 10)

    def test_reader_bad_message_length_too_large(self) -> None:
        """Test reader_async() generates bad message length error for too large"""
        # Length 65535 (the largest the field holds, above the 4096 maximum)
        header_data = Message.MARKER + struct.pack('!H', 65535) + b'\x01'

        length, msg_type, header, body, error = read_message(header_data)

        assert error is not None
        assert isinstance(error, NotifyError)
        assert error.code == 1  # Message Header Error
        assert error.subcode == 2  # Bad Message Length
        # RFC 4271 6.1: the Data field "MUST contain the erroneous Length field"
        assert error.data == struct.pack('!H', 65535)


class TestConcurrentReaderWriter:
    """Test concurrent reader and writer operations"""


class TestMessageTypeValidation:
    """Test validation of different BGP message types"""

    def test_reader_accepts_notification_message(self) -> None:
        """Test reader_async() accepts NOTIFICATION message"""
        header_data = Message.MARKER + struct.pack('!H', 21) + bytes([3])
        body_data = b'\x01\x01'  # Error code and subcode

        length, msg_type, header, body, error = read_message(header_data + body_data)

        assert error is None
        assert length == 21
        assert msg_type == 3
        assert header == header_data
        assert body == body_data

    def test_reader_accepts_route_refresh_message(self) -> None:
        """Test reader_async() accepts ROUTE_REFRESH message"""
        header_data = Message.MARKER + struct.pack('!H', 23) + bytes([5])
        body_data = b'\x00\x01\x00\x01'  # AFI, Reserved, SAFI

        length, msg_type, header, body, error = read_message(header_data + body_data)

        assert error is None
        assert length == 23
        assert msg_type == 5
        assert header == header_data
        assert body == body_data


class TestEdgeCasesAndDefensiveMode:
    """Test edge cases and defensive mode error injection"""

    def test_reader_handles_undefined_socket_error(self) -> None:
        """Test _reader_async() handles undefined socket errors"""
        conn = Connection(AFI.ipv4, '192.0.2.1', '192.0.2.2')

        mock_sock = Mock()
        mock_sock.fileno.return_value = 5
        conn.io = mock_sock
        mock_sock.recv_into.side_effect = OSError(999, 'Undefined error')

        with patch('exabgp.reactor.network.connection.log'):
            with pytest.raises(NetworkError) as exc_info:
                asyncio.run(conn._reader_async(10))

        assert 'Problem while reading data' in str(exc_info.value)

    def test_writer_handles_undefined_socket_error(self) -> None:
        """Test writer() handles undefined socket errors"""
        conn = Connection(AFI.ipv4, '192.0.2.1', '192.0.2.2')

        mock_sock = Mock()
        mock_sock.fileno.return_value = 5
        conn.io = mock_sock

        # Create an undefined socket error (not in block, fatal, or EPIPE)
        error = OSError(999, 'Undefined error')
        error.errno = 999
        mock_sock.send.side_effect = error

        with patch('select.poll') as mock_poll:
            mock_poller = Mock()
            mock_poller.poll.return_value = [(5, 4)]
            mock_poll.return_value = mock_poller

            with patch('exabgp.reactor.network.connection.log'):
                with patch('exabgp.reactor.network.connection.log'):
                    gen = conn.writer(b'test')

                    # Should yield False and continue (not raise)
                    results = []
                    for result in gen:
                        results.append(result)
                        # Break after a few iterations to avoid infinite loop
                        if len(results) > 10:
                            break

                    # Should have yielded at least one False
                    assert False in results

    def test_reader_keeps_no_state_after_notify_error(self) -> None:
        """Test reader_async() keeps no half read message after NotifyError"""
        invalid_header = b'\x00' * 16 + struct.pack('!H', 19) + b'\x04'
        keepalive = Message.MARKER + struct.pack('!H', 19) + b'\x04'

        refused, following = read_messages(invalid_header + keepalive, 2)

        assert isinstance(refused[4], NotifyError)
        # The next read parses the next header, not a body the refused header promised
        assert following[:2] == (19, 4)
        assert following[4] is None

    def test_reader_keeps_no_state_after_invalid_length(self) -> None:
        """Test reader_async() keeps no half read message after an invalid length"""
        invalid_header = Message.MARKER + struct.pack('!H', 18) + b'\x01'
        keepalive = Message.MARKER + struct.pack('!H', 19) + b'\x04'

        refused, following = read_messages(invalid_header + keepalive, 2)

        assert isinstance(refused[4], NotifyError)
        # The next read parses the next header, not a body the refused header promised
        assert following[:2] == (19, 4)
        assert following[4] is None

    def test_reader_keeps_no_state_after_validator_failure(self) -> None:
        """Test reader_async() keeps no half read message after the message type check fails"""
        invalid_header = Message.MARKER + struct.pack('!H', 22) + b'\x02'
        keepalive = Message.MARKER + struct.pack('!H', 19) + b'\x04'

        refused, following = read_messages(invalid_header + keepalive, 2)

        assert isinstance(refused[4], NotifyError)
        # The next read parses the next header, not a body the refused header promised
        assert following[:2] == (19, 4)
        assert following[4] is None

    def test_writing_returns_false_when_not_ready(self) -> None:
        """Test writing() returns False when socket not writable"""
        conn = Connection(AFI.ipv4, '192.0.2.1', '192.0.2.2')

        mock_sock = Mock()
        mock_sock.fileno.return_value = 5
        conn.io = mock_sock

        with patch('select.poll') as mock_poll:
            mock_poller = Mock()
            # Return empty list - no events
            mock_poller.poll.return_value = []
            mock_poll.return_value = mock_poller

            result = conn.writing()

            assert result is False

    def test_writing_detects_pollnval(self) -> None:
        """Test writing() detects POLLNVAL event and clears poller"""
        conn = Connection(AFI.ipv4, '192.0.2.1', '192.0.2.2')

        mock_sock = Mock()
        mock_sock.fileno.return_value = 5
        conn.io = mock_sock

        with patch('select.poll') as mock_poll:
            import select

            mock_poller = Mock()
            mock_poller.poll.return_value = [(5, select.POLLNVAL)]
            mock_poll.return_value = mock_poller

            result = conn.writing()

            assert result is True
            assert conn._wpoller == {}


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
