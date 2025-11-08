#!/usr/bin/env python3
# encoding: utf-8
"""
test_connection_advanced.py

Advanced tests for network connection layer functionality.
Tests async I/O, BGP message validation, multi-packet assembly, and buffer management.

Created: 2025-11-08
Updated: 2025-11-08 - Adapted for async/await architecture
"""

import pytest
import os
import socket
import struct
import asyncio
from unittest.mock import Mock, MagicMock, patch, call, AsyncMock

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
    """Test _reader() async I/O method"""

    @pytest.mark.asyncio
    async def test_reader_no_socket_raises_not_connected(self):
        """Test _reader() raises NotConnected when no socket"""
        conn = Connection(AFI.ipv4, '192.0.2.1', '192.0.2.2')

        with pytest.raises(NotConnected) as exc_info:
            await conn._reader(10)

        assert 'closed TCP connection' in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_reader_zero_bytes_yields_empty(self):
        """Test _reader(0) returns empty bytes immediately"""
        conn = Connection(AFI.ipv4, '192.0.2.1', '192.0.2.2')
        conn.io = Mock()

        result = await conn._reader(0)

        assert result == b''
        # Should not call recv for zero bytes
        conn.io.recv.assert_not_called()

    @pytest.mark.asyncio
    async def test_reader_waits_for_socket_ready(self):
        """Test _reader() awaits and reads data"""
        conn = Connection(AFI.ipv4, '192.0.2.1', '192.0.2.2')

        mock_sock = Mock()
        mock_sock.fileno.return_value = 5
        conn.io = mock_sock

        # Mock the asyncio event loop
        mock_loop = AsyncMock()
        mock_loop.sock_recv = AsyncMock(return_value=b'test')

        with patch('asyncio.get_event_loop', return_value=mock_loop):
            with patch('exabgp.reactor.network.connection.logfunc'):
                result = await conn._reader(4)
                assert result == b'test'
                mock_loop.sock_recv.assert_called_once_with(mock_sock, 4)

    @pytest.mark.asyncio
    async def test_reader_assembles_partial_reads(self):
        """Test _reader() assembles data from multiple recv() calls"""
        conn = Connection(AFI.ipv4, '192.0.2.1', '192.0.2.2')

        mock_sock = Mock()
        mock_sock.fileno.return_value = 5
        conn.io = mock_sock

        # Simulate partial reads: request 10 bytes, get 4, then 6
        mock_loop = AsyncMock()
        mock_loop.sock_recv = AsyncMock(side_effect=[b'test', b'data12'])

        with patch('asyncio.get_event_loop', return_value=mock_loop):
            with patch('exabgp.reactor.network.connection.logfunc'):
                result = await conn._reader(10)

                assert result == b'testdata12'
                assert mock_loop.sock_recv.call_count == 2

    @pytest.mark.asyncio
    async def test_reader_handles_blocking_error(self):
        """Test _reader() handles EAGAIN/EWOULDBLOCK errors"""
        conn = Connection(AFI.ipv4, '192.0.2.1', '192.0.2.2')

        mock_sock = Mock()
        mock_sock.fileno.return_value = 5
        conn.io = mock_sock

        # First call raises EAGAIN, second succeeds
        mock_loop = AsyncMock()
        mock_loop.sock_recv = AsyncMock(side_effect=[
            socket.error(errno.EAGAIN, 'Would block'),
            b'data'
        ])

        with patch('asyncio.get_event_loop', return_value=mock_loop):
            with patch('asyncio.sleep', new_callable=AsyncMock):  # Mock asyncio.sleep
                with patch('exabgp.reactor.network.connection.log'):
                    with patch('exabgp.reactor.network.connection.logfunc'):
                        result = await conn._reader(4)
                        assert result == b'data'

    @pytest.mark.asyncio
    async def test_reader_raises_lost_connection_on_empty_recv(self):
        """Test _reader() raises LostConnection when recv returns empty"""
        conn = Connection(AFI.ipv4, '192.0.2.1', '192.0.2.2')

        mock_sock = Mock()
        mock_sock.fileno.return_value = 5
        conn.io = mock_sock

        mock_loop = AsyncMock()
        mock_loop.sock_recv = AsyncMock(return_value=b'')  # Connection closed

        with patch('asyncio.get_event_loop', return_value=mock_loop):
            with patch('exabgp.reactor.network.connection.log'):
                with pytest.raises(LostConnection) as exc_info:
                    await conn._reader(10)

                assert 'closed by the remote end' in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_reader_raises_too_slow_on_timeout(self):
        """Test _reader() raises TooSlowError on socket timeout"""
        conn = Connection(AFI.ipv4, '192.0.2.1', '192.0.2.2')

        mock_sock = Mock()
        mock_sock.fileno.return_value = 5
        conn.io = mock_sock

        mock_loop = AsyncMock()
        mock_loop.sock_recv = AsyncMock(side_effect=socket.timeout('timed out'))

        with patch('asyncio.get_event_loop', return_value=mock_loop):
            with patch('exabgp.reactor.network.connection.log'):
                with pytest.raises(TooSlowError) as exc_info:
                    await conn._reader(10)

                assert 'Timeout' in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_reader_raises_lost_connection_on_fatal_error(self):
        """Test _reader() raises LostConnection on fatal socket errors"""
        conn = Connection(AFI.ipv4, '192.0.2.1', '192.0.2.2')

        mock_sock = Mock()
        mock_sock.fileno.return_value = 5
        conn.io = mock_sock

        mock_loop = AsyncMock()
        mock_loop.sock_recv = AsyncMock(side_effect=socket.error(errno.ECONNRESET, 'Connection reset'))

        with patch('asyncio.get_event_loop', return_value=mock_loop):
            with patch('exabgp.reactor.network.connection.log'):
                with pytest.raises(LostConnection):
                    await conn._reader(10)


class TestGeneratorBasedWriter:
    """Test writer() generator-based I/O method"""

    def test_writer_no_socket_yields_true(self):
        """Test writer() yields True immediately when no socket"""
        conn = Connection(AFI.ipv4, '192.0.2.1', '192.0.2.2')

        gen = conn.writer(b'test')
        result = next(gen)

        assert result is True

    def test_writer_waits_for_socket_ready(self):
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

            with patch('exabgp.reactor.network.connection.logfunc'):
                gen = conn.writer(b'test')

                # First yield should be False (waiting)
                result = next(gen)
                assert result is False

                # Second yield should be True (sent)
                result = next(gen)
                assert result is True

    def test_writer_partial_sends(self):
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

            with patch('exabgp.reactor.network.connection.logfunc'):
                gen = conn.writer(b'testdata12')

                results = []
                for result in gen:
                    results.append(result)

                # Should yield False after first partial send, True when complete
                assert False in results
                assert results[-1] is True
                assert mock_sock.send.call_count == 2

    def test_writer_handles_blocking_error(self):
        """Test writer() handles EAGAIN/EWOULDBLOCK errors"""
        conn = Connection(AFI.ipv4, '192.0.2.1', '192.0.2.2')

        mock_sock = Mock()
        mock_sock.fileno.return_value = 5
        conn.io = mock_sock

        # First call raises EAGAIN, second succeeds
        mock_sock.send.side_effect = [
            socket.error(errno.EAGAIN, 'Would block'),
            4
        ]

        with patch('select.poll') as mock_poll:
            mock_poller = Mock()
            mock_poller.poll.return_value = [(5, 4)]  # Always ready
            mock_poll.return_value = mock_poller

            with patch('exabgp.reactor.network.connection.log'):
                with patch('exabgp.reactor.network.connection.logfunc'):
                    gen = conn.writer(b'test')

                    results = []
                    for result in gen:
                        results.append(result)

                    # Should yield False on EAGAIN, then True
                    assert False in results
                    assert results[-1] is True

    def test_writer_raises_network_error_on_epipe(self):
        """Test writer() raises NetworkError on EPIPE (broken pipe)"""
        conn = Connection(AFI.ipv4, '192.0.2.1', '192.0.2.2')

        mock_sock = Mock()
        mock_sock.fileno.return_value = 5
        conn.io = mock_sock

        error = socket.error(errno.EPIPE, 'Broken pipe')
        error.errno = errno.EPIPE
        mock_sock.send.side_effect = error

        with patch('select.poll') as mock_poll:
            mock_poller = Mock()
            mock_poller.poll.return_value = [(5, 4)]
            mock_poll.return_value = mock_poller

            with patch('exabgp.reactor.network.connection.logfunc'):
                gen = conn.writer(b'test')

                with pytest.raises(NetworkError) as exc_info:
                    for _ in gen:
                        pass

                assert 'Broken TCP connection' in str(exc_info.value)

    def test_writer_raises_lost_connection_on_zero_send(self):
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
                with patch('exabgp.reactor.network.connection.logfunc'):
                    gen = conn.writer(b'test')

                    with pytest.raises(LostConnection):
                        for _ in gen:
                            pass


class TestBGPHeaderValidation:
    """Test BGP message header validation with error conditions"""

    def test_reader_validates_marker(self):
        """Test reader() validates BGP marker field"""
        conn = Connection(AFI.ipv4, '192.0.2.1', '192.0.2.2')

        # Invalid marker (all zeros instead of all 0xFF)
        invalid_header = b'\x00' * 16 + struct.pack('!H', 19) + b'\x04'

        def mock_reader(num_bytes):
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

    def test_reader_validates_length_minimum(self):
        """Test reader() rejects length < 19"""
        conn = Connection(AFI.ipv4, '192.0.2.1', '192.0.2.2')

        # Length = 18 (below minimum)
        invalid_header = Message.MARKER + struct.pack('!H', 18) + b'\x01'

        def mock_reader(num_bytes):
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

    def test_reader_validates_length_maximum(self):
        """Test reader() rejects length > msg_size"""
        conn = Connection(AFI.ipv4, '192.0.2.1', '192.0.2.2')

        # Length = 4097 (above default maximum of 4096)
        invalid_header = Message.MARKER + struct.pack('!H', 4097) + b'\x01'

        def mock_reader(num_bytes):
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

    def test_reader_validates_keepalive_length(self):
        """Test reader() validates KEEPALIVE must be exactly 19 bytes"""
        conn = Connection(AFI.ipv4, '192.0.2.1', '192.0.2.2')

        # KEEPALIVE with length 20 (should be exactly 19)
        invalid_header = Message.MARKER + struct.pack('!H', 20) + b'\x04'

        def mock_reader(num_bytes):
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

    def test_reader_validates_open_minimum_length(self):
        """Test reader() validates OPEN must be >= 29 bytes"""
        conn = Connection(AFI.ipv4, '192.0.2.1', '192.0.2.2')

        # OPEN with length 28 (below minimum of 29)
        invalid_header = Message.MARKER + struct.pack('!H', 28) + b'\x01'

        def mock_reader(num_bytes):
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

    def test_reader_validates_update_minimum_length(self):
        """Test reader() validates UPDATE must be >= 23 bytes"""
        conn = Connection(AFI.ipv4, '192.0.2.1', '192.0.2.2')

        # UPDATE with length 22 (below minimum of 23)
        invalid_header = Message.MARKER + struct.pack('!H', 22) + b'\x02'

        def mock_reader(num_bytes):
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

    def test_reader_accepts_valid_keepalive(self):
        """Test reader() accepts valid KEEPALIVE message"""
        conn = Connection(AFI.ipv4, '192.0.2.1', '192.0.2.2')

        # Valid KEEPALIVE: marker + length(19) + type(4)
        valid_header = Message.MARKER + struct.pack('!H', 19) + b'\x04'

        def mock_reader(num_bytes):
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

    def test_reader_assembles_message_with_body(self):
        """Test reader() assembles header and body into complete message"""
        conn = Connection(AFI.ipv4, '192.0.2.1', '192.0.2.2')

        # OPEN message with 10-byte body (total length 29)
        header_data = Message.MARKER + struct.pack('!H', 29) + b'\x01'
        body_data = b'\x04\xac\x10\x00\x01\x00\xb4\xc0\xa8\x01'  # 10 bytes

        reads = [header_data, body_data]
        read_index = [0]

        def mock_reader(num_bytes):
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

    def test_reader_handles_large_update_message(self):
        """Test reader() handles large UPDATE messages"""
        conn = Connection(AFI.ipv4, '192.0.2.1', '192.0.2.2')

        # Large UPDATE message (1000 bytes total)
        body_size = 1000 - 19
        header_data = Message.MARKER + struct.pack('!H', 1000) + b'\x02'
        body_data = b'\x00' * body_size

        reads = [header_data, body_data]
        read_index = [0]

        def mock_reader(num_bytes):
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

    def test_reader_yields_waiting_during_assembly(self):
        """Test reader() yields waiting state during message assembly"""
        conn = Connection(AFI.ipv4, '192.0.2.1', '192.0.2.2')

        header_data = Message.MARKER + struct.pack('!H', 29) + b'\x01'
        body_data = b'\x00' * 10

        # Simulate waiting by yielding empty first, then data
        call_count = [0]

        def mock_reader(num_bytes):
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

    def test_reader_handles_incremental_header_reads(self):
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

            with patch('exabgp.reactor.network.connection.logfunc'):
                gen = conn._reader(19)

                result = b''
                for data in gen:
                    if data:
                        result = data
                        break

                assert result == header_bytes
                assert mock_sock.recv.call_count == 19

    def test_reader_handles_variable_chunk_sizes(self):
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
            b'l'
        ]
        mock_sock.recv.side_effect = recv_results

        with patch('select.poll') as mock_poll:
            mock_poller = Mock()
            mock_poller.poll.return_value = [(5, 1)]  # Always ready
            mock_poll.return_value = mock_poller

            with patch('exabgp.reactor.network.connection.logfunc'):
                gen = conn._reader(20)

                result = b''
                for data in gen:
                    if data:
                        result = data
                        break

                assert result == b'12345678abcdefghijkl'
                assert mock_sock.recv.call_count == 5

    def test_writer_handles_incremental_sends(self):
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

            with patch('exabgp.reactor.network.connection.logfunc'):
                gen = conn.writer(data)

                results = []
                for result in gen:
                    results.append(result)

                # Should eventually yield True
                assert results[-1] is True
                assert mock_sock.send.call_count == 4

    def test_reader_buffer_boundary_conditions(self):
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

            with patch('exabgp.reactor.network.connection.logfunc'):
                gen = conn._reader(100)

                result = b''
                for chunk in gen:
                    if chunk:
                        result = chunk
                        break

                assert result == data
                assert len(result) == 100

    def test_reader_empty_body_message(self):
        """Test reader() handles message with no body (header only)"""
        conn = Connection(AFI.ipv4, '192.0.2.1', '192.0.2.2')

        # KEEPALIVE has no body, just header
        header_data = Message.MARKER + struct.pack('!H', 19) + b'\x04'

        def mock_reader(num_bytes):
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

    def test_reading_registers_poller_once(self):
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

    def test_writing_registers_poller_once(self):
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

    def test_reading_detects_hangup(self):
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

    def test_writing_detects_error(self):
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


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
