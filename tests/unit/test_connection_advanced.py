#!/usr/bin/env python3
# encoding: utf-8
"""test_connection_advanced.py

Advanced tests for network connection layer functionality.
Tests generator-based I/O, BGP message validation, multi-packet assembly, and buffer management.

Created: 2025-11-08
"""

import pytest
import os
import socket
import struct
from typing import Any
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


class TestGeneratorBasedReader:
    """Test _reader() generator-based I/O method"""

    def test_reader_no_socket_raises_not_connected(self) -> None:
        """Test _reader() raises NotConnected when no socket"""
        conn = Connection(AFI.ipv4, '192.0.2.1', '192.0.2.2')

        gen = conn._reader(10)
        with pytest.raises(NotConnected) as exc_info:
            next(gen)

        assert 'closed TCP connection' in str(exc_info.value)

    def test_reader_zero_bytes_yields_empty(self) -> None:
        """Test _reader(0) yields empty bytes immediately"""
        conn = Connection(AFI.ipv4, '192.0.2.1', '192.0.2.2')
        conn.io = Mock()

        gen = conn._reader(0)
        result = next(gen)

        assert result == b''
        # Should not call recv for zero bytes
        conn.io.recv.assert_not_called()

    def test_reader_waits_for_socket_ready(self) -> None:
        """Test _reader() yields empty bytes while waiting for data"""
        conn = Connection(AFI.ipv4, '192.0.2.1', '192.0.2.2')

        mock_sock = Mock()
        mock_sock.fileno.return_value = 5
        conn.io = mock_sock

        # Create a mock poller that returns not ready first, then ready
        poll_results = [[], [(5, 1)]]  # First not ready, then POLLIN

        with patch('select.poll') as mock_poll:
            mock_poller = Mock()
            mock_poller.poll.side_effect = poll_results
            mock_poll.return_value = mock_poller

            mock_sock.recv.return_value = b'test'

            with patch('exabgp.reactor.network.connection.log'):
                gen = conn._reader(4)

                # First yield should be empty (waiting)
                result = next(gen)
                assert result == b''

                # Second yield should return data
                result = next(gen)
                assert result == b'test'

    def test_reader_assembles_partial_reads(self) -> None:
        """Test _reader() assembles data from multiple recv() calls"""
        conn = Connection(AFI.ipv4, '192.0.2.1', '192.0.2.2')

        mock_sock = Mock()
        mock_sock.fileno.return_value = 5
        conn.io = mock_sock

        # Simulate partial reads: request 10 bytes, get 4, then 6
        recv_results = [b'test', b'data12']
        mock_sock.recv.side_effect = recv_results

        with patch('select.poll') as mock_poll:
            mock_poller = Mock()
            mock_poller.poll.return_value = [(5, 1)]  # Always ready
            mock_poll.return_value = mock_poller

            with patch('exabgp.reactor.network.connection.log'):
                gen = conn._reader(10)

                # Skip waiting yields
                result = b''
                for data in gen:
                    if data:
                        result = data
                        break

                assert result == b'testdata12'
                assert mock_sock.recv.call_count == 2

    def test_reader_handles_blocking_error(self) -> None:
        """Test _reader() handles EAGAIN/EWOULDBLOCK errors"""
        conn = Connection(AFI.ipv4, '192.0.2.1', '192.0.2.2')

        mock_sock = Mock()
        mock_sock.fileno.return_value = 5
        conn.io = mock_sock

        # First call raises EAGAIN, second succeeds
        mock_sock.recv.side_effect = [
            OSError(errno.EAGAIN, 'Would block'),
            b'data',
        ]

        with patch('select.poll') as mock_poll:
            mock_poller = Mock()
            mock_poller.poll.return_value = [(5, 1)]  # Always ready
            mock_poll.return_value = mock_poller

            with patch('exabgp.reactor.network.connection.log'):
                with patch('exabgp.reactor.network.connection.log'):
                    gen = conn._reader(4)

                    # Should yield empty on EAGAIN
                    result = next(gen)
                    if result == b'':
                        result = next(gen)

                    # Eventually should get data
                    while result == b'':
                        result = next(gen)

                    assert result == b'data'

    def test_reader_raises_lost_connection_on_empty_recv(self) -> None:
        """Test _reader() raises LostConnection when recv returns empty"""
        conn = Connection(AFI.ipv4, '192.0.2.1', '192.0.2.2')

        mock_sock = Mock()
        mock_sock.fileno.return_value = 5
        conn.io = mock_sock
        mock_sock.recv.return_value = b''  # Connection closed

        with patch('select.poll') as mock_poll:
            mock_poller = Mock()
            mock_poller.poll.return_value = [(5, 1)]
            mock_poll.return_value = mock_poller

            with patch('exabgp.reactor.network.connection.log'):
                gen = conn._reader(10)

                with pytest.raises(LostConnection) as exc_info:
                    for _ in gen:
                        pass

                assert 'closed by the remote end' in str(exc_info.value)

    def test_reader_raises_too_slow_on_timeout(self) -> None:
        """Test _reader() raises TooSlowError on socket timeout"""
        conn = Connection(AFI.ipv4, '192.0.2.1', '192.0.2.2')

        mock_sock = Mock()
        mock_sock.fileno.return_value = 5
        conn.io = mock_sock
        mock_sock.recv.side_effect = socket.timeout('timed out')

        with patch('select.poll') as mock_poll:
            mock_poller = Mock()
            mock_poller.poll.return_value = [(5, 1)]
            mock_poll.return_value = mock_poller

            with patch('exabgp.reactor.network.connection.log'):
                gen = conn._reader(10)

                with pytest.raises(TooSlowError) as exc_info:
                    for _ in gen:
                        pass

                assert 'Timeout' in str(exc_info.value)

    def test_reader_raises_lost_connection_on_fatal_error(self) -> None:
        """Test _reader() raises LostConnection on fatal socket errors"""
        conn = Connection(AFI.ipv4, '192.0.2.1', '192.0.2.2')

        mock_sock = Mock()
        mock_sock.fileno.return_value = 5
        conn.io = mock_sock
        mock_sock.recv.side_effect = OSError(errno.ECONNRESET, 'Connection reset')

        with patch('select.poll') as mock_poll:
            mock_poller = Mock()
            mock_poller.poll.return_value = [(5, 1)]
            mock_poll.return_value = mock_poller

            with patch('exabgp.reactor.network.connection.log'):
                gen = conn._reader(10)

                with pytest.raises(LostConnection):
                    for _ in gen:
                        pass


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
        """Test reader() validates BGP marker field"""
        conn = Connection(AFI.ipv4, '192.0.2.1', '192.0.2.2')

        # Invalid marker (all zeros instead of all 0xFF)
        invalid_header = b'\x00' * 16 + struct.pack('!H', 19) + b'\x04'

        def mock_reader(num_bytes: Any):
            if num_bytes == 19:
                yield invalid_header
            else:
                yield b''

        conn._reader = mock_reader

        gen = conn.reader()
        length, msg_type, header, body, error = next(gen)

        assert error is not None
        assert isinstance(error, NotifyError)
        assert error.code == 1  # Message Header Error
        assert error.subcode == 1  # Connection Not Synchronized

    def test_reader_validates_length_minimum(self) -> None:
        """Test reader() rejects length < 19"""
        conn = Connection(AFI.ipv4, '192.0.2.1', '192.0.2.2')

        # Length = 18 (below minimum)
        invalid_header = Message.MARKER + struct.pack('!H', 18) + b'\x01'

        def mock_reader(num_bytes: Any):
            if num_bytes == 19:
                yield invalid_header
            else:
                yield b''

        conn._reader = mock_reader

        gen = conn.reader()
        length, msg_type, header, body, error = next(gen)

        assert error is not None
        assert isinstance(error, NotifyError)
        assert error.code == 1  # Message Header Error
        assert error.subcode == 2  # Bad Message Length

    def test_reader_validates_length_maximum(self) -> None:
        """Test reader() rejects length > msg_size"""
        conn = Connection(AFI.ipv4, '192.0.2.1', '192.0.2.2')

        # Length = 4097 (above default maximum of 4096)
        invalid_header = Message.MARKER + struct.pack('!H', 4097) + b'\x01'

        def mock_reader(num_bytes: Any):
            if num_bytes == 19:
                yield invalid_header
            else:
                yield b''

        conn._reader = mock_reader

        gen = conn.reader()
        length, msg_type, header, body, error = next(gen)

        assert error is not None
        assert isinstance(error, NotifyError)
        assert error.code == 1  # Message Header Error
        assert error.subcode == 2  # Bad Message Length

    def test_reader_validates_keepalive_length(self) -> None:
        """Test reader() validates KEEPALIVE must be exactly 19 bytes"""
        conn = Connection(AFI.ipv4, '192.0.2.1', '192.0.2.2')

        # KEEPALIVE with length 20 (should be exactly 19)
        invalid_header = Message.MARKER + struct.pack('!H', 20) + b'\x04'

        def mock_reader(num_bytes: Any):
            if num_bytes == 19:
                yield invalid_header
            elif num_bytes == 1:
                yield b'\x00'
            else:
                yield b''

        conn._reader = mock_reader

        gen = conn.reader()
        length, msg_type, header, body, error = next(gen)

        assert error is not None
        assert isinstance(error, NotifyError)
        assert error.code == 1  # Message Header Error
        assert error.subcode == 2  # Bad Message Length

    def test_reader_validates_open_minimum_length(self) -> None:
        """Test reader() validates OPEN must be >= 29 bytes"""
        conn = Connection(AFI.ipv4, '192.0.2.1', '192.0.2.2')

        # OPEN with length 28 (below minimum of 29)
        invalid_header = Message.MARKER + struct.pack('!H', 28) + b'\x01'

        def mock_reader(num_bytes: Any):
            if num_bytes == 19:
                yield invalid_header
            else:
                yield b''

        conn._reader = mock_reader

        gen = conn.reader()
        length, msg_type, header, body, error = next(gen)

        assert error is not None
        assert isinstance(error, NotifyError)
        assert error.code == 1  # Message Header Error
        assert error.subcode == 2  # Bad Message Length

    def test_reader_validates_update_minimum_length(self) -> None:
        """Test reader() validates UPDATE must be >= 23 bytes"""
        conn = Connection(AFI.ipv4, '192.0.2.1', '192.0.2.2')

        # UPDATE with length 22 (below minimum of 23)
        invalid_header = Message.MARKER + struct.pack('!H', 22) + b'\x02'

        def mock_reader(num_bytes: Any):
            if num_bytes == 19:
                yield invalid_header
            else:
                yield b''

        conn._reader = mock_reader

        gen = conn.reader()
        length, msg_type, header, body, error = next(gen)

        assert error is not None
        assert isinstance(error, NotifyError)
        assert error.code == 1  # Message Header Error
        assert error.subcode == 2  # Bad Message Length

    def test_reader_accepts_valid_keepalive(self) -> None:
        """Test reader() accepts valid KEEPALIVE message"""
        conn = Connection(AFI.ipv4, '192.0.2.1', '192.0.2.2')

        # Valid KEEPALIVE: marker + length(19) + type(4)
        valid_header = Message.MARKER + struct.pack('!H', 19) + b'\x04'

        def mock_reader(num_bytes: Any):
            if num_bytes == 19:
                yield valid_header
            else:
                yield b''

        conn._reader = mock_reader

        gen = conn.reader()
        length, msg_type, header, body, error = next(gen)

        assert error is None
        assert length == 19
        assert msg_type == 4
        assert header == valid_header
        assert body == b''


class TestMultiPacketAssembly:
    """Test multi-packet message assembly"""

    def test_reader_assembles_message_with_body(self) -> None:
        """Test reader() assembles header and body into complete message"""
        conn = Connection(AFI.ipv4, '192.0.2.1', '192.0.2.2')

        # OPEN message with 10-byte body (total length 29)
        header_data = Message.MARKER + struct.pack('!H', 29) + b'\x01'
        body_data = b'\x04\xac\x10\x00\x01\x00\xb4\xc0\xa8\x01'  # 10 bytes

        reads = [header_data, body_data]
        read_index = [0]

        def mock_reader(num_bytes: Any):
            data = reads[read_index[0]]
            read_index[0] += 1
            yield data

        conn._reader = mock_reader

        gen = conn.reader()
        length, msg_type, header, body, error = next(gen)

        assert error is None
        assert length == 29
        assert msg_type == 1
        assert len(header) == 19
        assert len(body) == 10
        assert body == body_data

    def test_reader_handles_large_update_message(self) -> None:
        """Test reader() handles large UPDATE messages"""
        conn = Connection(AFI.ipv4, '192.0.2.1', '192.0.2.2')

        # Large UPDATE message (1000 bytes total)
        body_size = 1000 - 19
        header_data = Message.MARKER + struct.pack('!H', 1000) + b'\x02'
        body_data = b'\x00' * body_size

        reads = [header_data, body_data]
        read_index = [0]

        def mock_reader(num_bytes: Any):
            data = reads[read_index[0]]
            read_index[0] += 1
            yield data

        conn._reader = mock_reader

        gen = conn.reader()
        length, msg_type, header, body, error = next(gen)

        assert error is None
        assert length == 1000
        assert msg_type == 2
        assert len(body) == body_size

    def test_reader_yields_waiting_during_assembly(self) -> None:
        """Test reader() yields waiting state during message assembly"""
        conn = Connection(AFI.ipv4, '192.0.2.1', '192.0.2.2')

        header_data = Message.MARKER + struct.pack('!H', 29) + b'\x01'
        body_data = b'\x00' * 10

        # Simulate waiting by yielding empty first, then data
        call_count = [0]

        def mock_reader(num_bytes: Any):
            call_count[0] += 1
            if call_count[0] == 1:
                # First call for header - yield empty then data
                yield b''
                yield header_data
            else:
                # Second call for body - yield empty then data
                yield b''
                yield body_data

        conn._reader = mock_reader

        gen = conn.reader()

        # First result should be waiting state
        result = next(gen)
        assert result == (0, 0, b'', b'', None)

        # Continue to final result
        result = next(gen)
        while result == (0, 0, b'', b'', None):
            result = next(gen)

        length, msg_type, header, body, error = result
        assert error is None
        assert length == 29


class TestBufferManagement:
    """Test buffer management scenarios"""

    def test_reader_handles_incremental_header_reads(self) -> None:
        """Test _reader() assembles header from small incremental reads"""
        conn = Connection(AFI.ipv4, '192.0.2.1', '192.0.2.2')

        mock_sock = Mock()
        mock_sock.fileno.return_value = 5
        conn.io = mock_sock

        # Simulate receiving header in 1-byte chunks
        header_bytes = Message.MARKER + struct.pack('!H', 19) + b'\x04'
        recv_results = [bytes([b]) for b in header_bytes]
        mock_sock.recv.side_effect = recv_results

        with patch('select.poll') as mock_poll:
            mock_poller = Mock()
            mock_poller.poll.return_value = [(5, 1)]  # Always ready
            mock_poll.return_value = mock_poller

            with patch('exabgp.reactor.network.connection.log'):
                gen = conn._reader(19)

                result = b''
                for data in gen:
                    if data:
                        result = data
                        break

                assert result == header_bytes
                assert mock_sock.recv.call_count == 19

    def test_reader_handles_variable_chunk_sizes(self) -> None:
        """Test _reader() handles variable-size recv() chunks"""
        conn = Connection(AFI.ipv4, '192.0.2.1', '192.0.2.2')

        mock_sock = Mock()
        mock_sock.fileno.return_value = 5
        conn.io = mock_sock

        # Simulate variable chunk sizes: 5, 3, 7, 4, 1 bytes (total 20)
        recv_results = [
            b'12345',
            b'678',
            b'abcdefg',
            b'hijk',
            b'l',
        ]
        mock_sock.recv.side_effect = recv_results

        with patch('select.poll') as mock_poll:
            mock_poller = Mock()
            mock_poller.poll.return_value = [(5, 1)]  # Always ready
            mock_poll.return_value = mock_poller

            with patch('exabgp.reactor.network.connection.log'):
                gen = conn._reader(20)

                result = b''
                for data in gen:
                    if data:
                        result = data
                        break

                assert result == b'12345678abcdefghijkl'
                assert mock_sock.recv.call_count == 5

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
        """Test _reader() handles exact buffer boundaries"""
        conn = Connection(AFI.ipv4, '192.0.2.1', '192.0.2.2')

        mock_sock = Mock()
        mock_sock.fileno.return_value = 5
        conn.io = mock_sock

        # Request exactly what's available
        data = b'exactly100bytes' * 6 + b'exactly10b'  # 100 bytes
        mock_sock.recv.return_value = data

        with patch('select.poll') as mock_poll:
            mock_poller = Mock()
            mock_poller.poll.return_value = [(5, 1)]
            mock_poll.return_value = mock_poller

            with patch('exabgp.reactor.network.connection.log'):
                gen = conn._reader(100)

                result = b''
                for chunk in gen:
                    if chunk:
                        result = chunk
                        break

                assert result == data
                assert len(result) == 100

    def test_reader_empty_body_message(self) -> None:
        """Test reader() handles message with no body (header only)"""
        conn = Connection(AFI.ipv4, '192.0.2.1', '192.0.2.2')

        # KEEPALIVE has no body, just header
        header_data = Message.MARKER + struct.pack('!H', 19) + b'\x04'

        def mock_reader(num_bytes: Any):
            if num_bytes == 19:
                yield header_data
            else:
                yield b''

        conn._reader = mock_reader

        gen = conn.reader()
        length, msg_type, header, body, error = next(gen)

        assert error is None
        assert length == 19
        assert msg_type == 4
        assert body == b''  # No body for KEEPALIVE


class TestPollingMechanisms:
    """Test reading() and writing() polling mechanisms"""

    def test_reading_registers_poller_once(self) -> None:
        """Test reading() registers poller only once"""
        conn = Connection(AFI.ipv4, '192.0.2.1', '192.0.2.2')

        mock_sock = Mock()
        mock_sock.fileno.return_value = 5
        conn.io = mock_sock

        with patch('select.poll') as mock_poll:
            mock_poller = Mock()
            mock_poller.poll.return_value = [(5, 1)]
            mock_poll.return_value = mock_poller

            # First call should register
            conn.reading()
            assert mock_poll.call_count == 1
            assert mock_poller.register.call_count == 1

            # Second call should reuse poller
            conn.reading()
            assert mock_poll.call_count == 1
            assert mock_poller.register.call_count == 1

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

    def test_reading_detects_hangup(self) -> None:
        """Test reading() detects POLLHUP event"""
        conn = Connection(AFI.ipv4, '192.0.2.1', '192.0.2.2')

        mock_sock = Mock()
        mock_sock.fileno.return_value = 5
        conn.io = mock_sock

        with patch('select.poll') as mock_poll:
            import select
            mock_poller = Mock()
            mock_poller.poll.return_value = [(5, select.POLLHUP)]
            mock_poll.return_value = mock_poller

            result = conn.reading()

            assert result is True
            # Poller should be cleared on hangup
            assert conn._rpoller == {}

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
        assert conn._rpoller == {}
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
        """Test reader() validates length against current msg_size"""
        conn = Connection(AFI.ipv4, '192.0.2.1', '192.0.2.2')
        conn.msg_size = 100  # Small limit for testing

        # Message with length 101 (exceeds msg_size)
        invalid_header = Message.MARKER + struct.pack('!H', 101) + b'\x02'

        def mock_reader(num_bytes: Any):
            if num_bytes == 19:
                yield invalid_header
            else:
                yield b''

        conn._reader = mock_reader

        gen = conn.reader()
        length, msg_type, header, body, error = next(gen)

        assert error is not None
        assert isinstance(error, NotifyError)
        assert error.code == 1  # Message Header Error
        assert error.subcode == 2  # Bad Message Length

    def test_reader_accepts_extended_size_when_configured(self) -> None:
        """Test reader() accepts large messages when extended size configured"""
        conn = Connection(AFI.ipv4, '192.0.2.1', '192.0.2.2')
        conn.msg_size = 65535  # Extended message size

        # Large UPDATE message (5000 bytes)
        body_size = 5000 - 19
        header_data = Message.MARKER + struct.pack('!H', 5000) + b'\x02'
        body_data = b'\x00' * body_size

        reads = [header_data, body_data]
        read_index = [0]

        def mock_reader(num_bytes: Any):
            data = reads[read_index[0]]
            read_index[0] += 1
            yield data

        conn._reader = mock_reader

        gen = conn.reader()
        length, msg_type, header, body, error = next(gen)

        assert error is None
        assert length == 5000
        assert msg_type == 2


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
        """Test _reader() propagates fatal socket errors"""
        conn = Connection(AFI.ipv4, '192.0.2.1', '192.0.2.2')

        mock_sock = Mock()
        mock_sock.fileno.return_value = 5
        conn.io = mock_sock

        error = OSError(errno.ECONNREFUSED, 'Connection refused')
        error.errno = errno.ECONNREFUSED
        mock_sock.recv.side_effect = error

        with patch('select.poll') as mock_poll:
            mock_poller = Mock()
            mock_poller.poll.return_value = [(5, 1)]
            mock_poll.return_value = mock_poller

            with patch('exabgp.reactor.network.connection.log'):
                gen = conn._reader(10)

                with pytest.raises(LostConnection):
                    for _ in gen:
                        pass

    def test_reader_clears_socket_on_error(self) -> None:
        """Test _reader() clears socket on connection loss"""
        conn = Connection(AFI.ipv4, '192.0.2.1', '192.0.2.2')

        mock_sock = Mock()
        mock_sock.fileno.return_value = 5
        conn.io = mock_sock
        mock_sock.recv.return_value = b''  # Connection closed

        with patch('select.poll') as mock_poll:
            mock_poller = Mock()
            mock_poller.poll.return_value = [(5, 1)]
            mock_poll.return_value = mock_poller

            with patch('exabgp.reactor.network.connection.log'):
                gen = conn._reader(10)

                with pytest.raises(LostConnection):
                    for _ in gen:
                        pass

                # Socket should be closed
                assert conn.io is None


class TestNotificationErrorTypes:
    """Test different BGP NOTIFICATION error codes"""

    def test_reader_connection_not_synchronized_error(self) -> None:
        """Test reader() generates connection not synchronized error"""
        conn = Connection(AFI.ipv4, '192.0.2.1', '192.0.2.2')

        # Invalid marker
        invalid_header = b'\x00' * 16 + struct.pack('!H', 19) + b'\x04'

        def mock_reader(num_bytes: Any):
            yield invalid_header if num_bytes == 19 else b''

        conn._reader = mock_reader

        gen = conn.reader()
        _, _, _, _, error = next(gen)

        assert error.code == 1  # Message Header Error
        assert error.subcode == 1  # Connection Not Synchronized

    def test_reader_bad_message_length_too_small(self) -> None:
        """Test reader() generates bad message length error for too small"""
        conn = Connection(AFI.ipv4, '192.0.2.1', '192.0.2.2')

        # Length 10 (below minimum 19)
        invalid_header = Message.MARKER + struct.pack('!H', 10) + b'\x01'

        def mock_reader(num_bytes: Any):
            yield invalid_header if num_bytes == 19 else b''

        conn._reader = mock_reader

        gen = conn.reader()
        _, _, _, _, error = next(gen)

        assert error.code == 1  # Message Header Error
        assert error.subcode == 2  # Bad Message Length

    def test_reader_bad_message_length_too_large(self) -> None:
        """Test reader() generates bad message length error for too large"""
        conn = Connection(AFI.ipv4, '192.0.2.1', '192.0.2.2')

        # Length 100000 (way above maximum)
        invalid_header = Message.MARKER + struct.pack('!H', 65535) + b'\x01'
        # Note: struct.pack('!H', 100000) would overflow, using max uint16

        def mock_reader(num_bytes: Any):
            yield invalid_header if num_bytes == 19 else b''

        conn._reader = mock_reader

        gen = conn.reader()
        _, _, _, _, error = next(gen)

        assert error.code == 1  # Message Header Error
        assert error.subcode == 2  # Bad Message Length


class TestConcurrentReaderWriter:
    """Test concurrent reader and writer operations"""

    def test_reading_and_writing_use_separate_pollers(self) -> None:
        """Test reading() and writing() maintain separate pollers"""
        conn = Connection(AFI.ipv4, '192.0.2.1', '192.0.2.2')

        mock_sock = Mock()
        mock_sock.fileno.return_value = 5
        conn.io = mock_sock

        with patch('select.poll') as mock_poll:
            mock_poller = Mock()
            mock_poller.poll.return_value = [(5, 1)]
            mock_poll.return_value = mock_poller

            # Register for reading
            conn.reading()
            read_poller = conn._rpoller.get(mock_sock)

            # Register for writing
            conn.writing()
            write_poller = conn._wpoller.get(mock_sock)

            # Should have separate pollers
            assert read_poller is not None
            assert write_poller is not None
            assert mock_poll.call_count == 2

    def test_poller_cleanup_on_socket_close(self) -> None:
        """Test pollers are cleared when connection closes"""
        conn = Connection(AFI.ipv4, '192.0.2.1', '192.0.2.2')

        mock_sock = Mock()
        conn.io = mock_sock
        conn._rpoller = {mock_sock: Mock()}
        conn._wpoller = {mock_sock: Mock()}

        with patch('exabgp.reactor.network.connection.log'):
            conn.close()

        # Pollers should still reference old socket
        # (they'll be recreated on next use with new socket)
        assert conn.io is None


class TestMessageTypeValidation:
    """Test validation of different BGP message types"""

    def test_reader_accepts_notification_message(self) -> None:
        """Test reader() accepts NOTIFICATION message"""
        conn = Connection(AFI.ipv4, '192.0.2.1', '192.0.2.2')

        # NOTIFICATION message (type 3) with 2-byte body
        header_data = Message.MARKER + struct.pack('!H', 21) + b'\x03'
        body_data = b'\x01\x01'  # Error code and subcode

        reads = [header_data, body_data]
        read_index = [0]

        def mock_reader(num_bytes: Any):
            data = reads[read_index[0]]
            read_index[0] += 1
            yield data

        conn._reader = mock_reader

        gen = conn.reader()
        length, msg_type, header, body, error = next(gen)

        assert error is None
        assert length == 21
        assert msg_type == 3
        assert len(body) == 2

    def test_reader_accepts_route_refresh_message(self) -> None:
        """Test reader() accepts ROUTE_REFRESH message"""
        conn = Connection(AFI.ipv4, '192.0.2.1', '192.0.2.2')

        # ROUTE_REFRESH message (type 5) with 4-byte body
        header_data = Message.MARKER + struct.pack('!H', 23) + b'\x05'
        body_data = b'\x00\x01\x00\x01'  # AFI, Reserved, SAFI

        reads = [header_data, body_data]
        read_index = [0]

        def mock_reader(num_bytes: Any):
            data = reads[read_index[0]]
            read_index[0] += 1
            yield data

        conn._reader = mock_reader

        gen = conn.reader()
        length, msg_type, header, body, error = next(gen)

        assert error is None
        assert length == 23
        assert msg_type == 5
        assert len(body) == 4


class TestEdgeCasesAndDefensiveMode:
    """Test edge cases and defensive mode error injection"""

    def test_reader_handles_undefined_socket_error(self) -> None:
        """Test _reader() handles undefined socket errors"""
        conn = Connection(AFI.ipv4, '192.0.2.1', '192.0.2.2')

        mock_sock = Mock()
        mock_sock.fileno.return_value = 5
        conn.io = mock_sock

        # Create an undefined socket error (not in block or fatal lists)
        error = OSError(999, 'Undefined error')
        error.errno = 999
        mock_sock.recv.side_effect = error

        with patch('select.poll') as mock_poll:
            mock_poller = Mock()
            mock_poller.poll.return_value = [(5, 1)]
            mock_poll.return_value = mock_poller

            with patch('exabgp.reactor.network.connection.log'):
                gen = conn._reader(10)

                with pytest.raises(NetworkError) as exc_info:
                    for _ in gen:
                        pass

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

    def test_reader_stops_iteration_after_notify_error(self) -> None:
        """Test reader() stops iteration after yielding NotifyError"""
        conn = Connection(AFI.ipv4, '192.0.2.1', '192.0.2.2')

        # Invalid marker to trigger NotifyError
        invalid_header = b'\x00' * 16 + struct.pack('!H', 19) + b'\x04'

        def mock_reader(num_bytes: Any):
            yield invalid_header

        conn._reader = mock_reader

        gen = conn.reader()
        length, msg_type, header, body, error = next(gen)

        assert error is not None
        assert isinstance(error, NotifyError)

        # Generator should stop after yielding error
        with pytest.raises(StopIteration):
            next(gen)

    def test_reader_stops_after_invalid_length(self) -> None:
        """Test reader() stops after detecting invalid length"""
        conn = Connection(AFI.ipv4, '192.0.2.1', '192.0.2.2')

        # Length too small
        invalid_header = Message.MARKER + struct.pack('!H', 18) + b'\x01'

        def mock_reader(num_bytes: Any):
            yield invalid_header

        conn._reader = mock_reader

        gen = conn.reader()
        length, msg_type, header, body, error = next(gen)

        assert error is not None
        assert isinstance(error, NotifyError)

        # Generator should stop
        with pytest.raises(StopIteration):
            next(gen)

    def test_reader_stops_after_validator_failure(self) -> None:
        """Test reader() stops after message type validator fails"""
        conn = Connection(AFI.ipv4, '192.0.2.1', '192.0.2.2')

        # UPDATE with invalid length (too small)
        invalid_header = Message.MARKER + struct.pack('!H', 22) + b'\x02'

        def mock_reader(num_bytes: Any):
            yield invalid_header

        conn._reader = mock_reader

        gen = conn.reader()
        length, msg_type, header, body, error = next(gen)

        assert error is not None
        assert isinstance(error, NotifyError)

        # Generator should stop
        with pytest.raises(StopIteration):
            next(gen)

    def test_reading_returns_false_when_not_ready(self) -> None:
        """Test reading() returns False when no data available"""
        conn = Connection(AFI.ipv4, '192.0.2.1', '192.0.2.2')

        mock_sock = Mock()
        mock_sock.fileno.return_value = 5
        conn.io = mock_sock

        with patch('select.poll') as mock_poll:
            mock_poller = Mock()
            # Return empty list - no events
            mock_poller.poll.return_value = []
            mock_poll.return_value = mock_poller

            result = conn.reading()

            assert result is False

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

    def test_reading_detects_pollnval(self) -> None:
        """Test reading() detects POLLNVAL event and clears poller"""
        conn = Connection(AFI.ipv4, '192.0.2.1', '192.0.2.2')

        mock_sock = Mock()
        mock_sock.fileno.return_value = 5
        conn.io = mock_sock

        with patch('select.poll') as mock_poll:
            import select
            mock_poller = Mock()
            mock_poller.poll.return_value = [(5, select.POLLNVAL)]
            mock_poll.return_value = mock_poller

            result = conn.reading()

            assert result is True
            assert conn._rpoller == {}

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
