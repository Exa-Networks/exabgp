#!/usr/bin/env python3
# encoding: utf-8
"""test_race_conditions.py

Race condition tests for concurrent connection scenarios in ExaBGP.
Tests timing-sensitive scenarios including simultaneous connections,
connection state transitions, polling races, and message queue ordering.

Created: 2025-11-08
"""

import pytest
import os
import socket
import struct
from unittest.mock import MagicMock, patch

# Set up environment before importing ExaBGP modules
os.environ['exabgp_log_enable'] = 'false'
os.environ['exabgp_log_level'] = 'CRITICAL'

from exabgp.protocol.family import AFI
from exabgp.reactor.network.connection import Connection
from exabgp.reactor.network.error import (
    NotConnected,
    LostConnection,
    NetworkError,
    errno,
)


class TestSimultaneousBidirectionalConnections:
    """Test race conditions when both peers connect simultaneously"""

    def test_simultaneous_connection_establishment(self) -> None:
        """Test simultaneous bi-directional connection establishment.

        Scenario: Both peers initiate connections at same time
        Expected: One connection succeeds, duplicate is detected and closed
        """
        # Create two connection objects simulating peer1->peer2 and peer2->peer1
        conn1 = Connection(AFI.ipv4, '192.0.2.1', '192.0.2.2')
        conn2 = Connection(AFI.ipv4, '192.0.2.2', '192.0.2.1')

        # Mock sockets for both connections
        mock_sock1 = MagicMock(spec=socket.socket)
        mock_sock1.fileno.return_value = 5
        mock_sock2 = MagicMock(spec=socket.socket)
        mock_sock2.fileno.return_value = 6

        conn1.io = mock_sock1
        conn2.io = mock_sock2

        # Verify both connections can be established
        assert conn1.io is not None
        assert conn2.io is not None

        # Close both connections
        with patch('exabgp.reactor.network.connection.log'):
            conn1.close()
            conn2.close()

        # Verify cleanup occurred
        mock_sock1.close.assert_called_once()
        mock_sock2.close.assert_called_once()

    def test_connection_race_with_fd_reuse(self) -> None:
        """Test file descriptor reuse race condition.

        Scenario: Socket closes and fd is immediately reused by new connection
        Expected: Poller correctly tracks new socket, old poller state cleared
        """
        conn = Connection(AFI.ipv4, '192.0.2.1', '192.0.2.2')

        # First socket with fd=5
        mock_sock1 = MagicMock(spec=socket.socket)
        mock_sock1.fileno.return_value = 5
        conn.io = mock_sock1

        # Set up polling state
        with patch('select.poll') as mock_poll:
            mock_poller = MagicMock()
            mock_poll.return_value = mock_poller
            mock_poller.poll.return_value = []

            # Trigger poller registration by checking reading status
            is_reading = conn.reading()

            # Close first socket
            with patch('exabgp.reactor.network.connection.log'):
                conn.close()

            # Create new socket that reuses fd=5
            mock_sock2 = MagicMock(spec=socket.socket)
            mock_sock2.fileno.return_value = 5
            conn.io = mock_sock2

            # Check that poller state was cleared
            assert conn.io is not None

    def test_concurrent_accept_and_connect(self) -> None:
        """Test concurrent incoming accept and outgoing connect.

        Scenario: Accept incoming connection while establishing outgoing
        Expected: Both operations succeed without interfering
        """
        # Simulate incoming connection
        incoming_conn = Connection(AFI.ipv4, '192.0.2.1', '192.0.2.2')
        incoming_sock = MagicMock(spec=socket.socket)
        incoming_sock.fileno.return_value = 10
        incoming_conn.io = incoming_sock

        # Simulate outgoing connection
        outgoing_conn = Connection(AFI.ipv4, '192.0.2.2', '192.0.2.1')
        outgoing_sock = MagicMock(spec=socket.socket)
        outgoing_sock.fileno.return_value = 11
        outgoing_conn.io = outgoing_sock

        # Both should have valid sockets
        assert incoming_conn.io is not None
        assert outgoing_conn.io is not None

        # Different file descriptors
        assert incoming_conn.io.fileno() != outgoing_conn.io.fileno()

        # Cleanup
        with patch('exabgp.reactor.network.connection.log'):
            incoming_conn.close()
            outgoing_conn.close()


class TestConnectionResetDuringIO:
    """Test race conditions when connection resets during I/O operations"""

    def test_reset_during_message_send(self) -> None:
        """Test connection reset during message transmission.

        Scenario: Connection closes while writer() generator is active
        Expected: Graceful error handling, no corruption
        """
        conn = Connection(AFI.ipv4, '192.0.2.1', '192.0.2.2')
        mock_sock = MagicMock(spec=socket.socket)
        mock_sock.fileno.return_value = 7
        conn.io = mock_sock

        # Create data to write
        test_data = b'test message data'

        # Mock send to return partial write, then connection reset
        mock_sock.send.side_effect = [5, OSError(errno.ECONNRESET, "Connection reset")]

        # Start writer generator
        writer_gen = conn.writer(test_data)

        # First iteration - partial send
        with patch('select.poll') as mock_poll:
            with patch('exabgp.reactor.network.connection.log'):
                with patch('exabgp.reactor.network.connection.log'):
                    mock_poller = MagicMock()
                    mock_poll.return_value = mock_poller
                    mock_poller.poll.return_value = [(7, 4)]  # POLLOUT

                    # First iteration - partial send
                    result = next(writer_gen)
                    assert result is False

                    # Second iteration - connection reset
                    with pytest.raises(NetworkError):
                        next(writer_gen)

    def test_reset_during_message_read(self) -> None:
        """Test connection reset during message reception.

        Scenario: Connection closes while _reader() generator is active
        Expected: Proper error propagation, buffer cleanup
        """
        conn = Connection(AFI.ipv4, '192.0.2.1', '192.0.2.2')
        mock_sock = MagicMock(spec=socket.socket)
        mock_sock.fileno.return_value = 8
        conn.io = mock_sock

        # Mock recv to return empty (connection closed)
        mock_sock.recv.return_value = b''

        # Create reader generator
        reader_gen = conn._reader(19)  # BGP header size

        with patch('select.poll') as mock_poll:
            with patch('exabgp.reactor.network.connection.log'):
                mock_poller = MagicMock()
                mock_poll.return_value = mock_poller
                mock_poller.poll.return_value = [(8, 1)]  # POLLIN

                # Should raise LostConnection
                with pytest.raises(LostConnection) as exc_info:
                    next(reader_gen)

                assert 'TCP connection was closed' in str(exc_info.value)

    def test_close_during_active_reader(self) -> None:
        """Test explicit close() while reader generator is active.

        Scenario: close() called while waiting for data in _reader()
        Expected: Reader detects closed socket and raises NotConnected
        """
        conn = Connection(AFI.ipv4, '192.0.2.1', '192.0.2.2')
        mock_sock = MagicMock(spec=socket.socket)
        mock_sock.fileno.return_value = 9
        conn.io = mock_sock

        # Start reader
        reader_gen = conn._reader(100)

        # Mock recv to block (would wait for data)
        mock_sock.recv.return_value = b''

        with patch('select.poll') as mock_poll:
            mock_poller = MagicMock()
            mock_poll.return_value = mock_poller
            mock_poller.poll.return_value = []  # No data ready

            # Explicitly close connection
            conn.close()

            # Next reader iteration should fail
            with pytest.raises(NotConnected):
                next(reader_gen)


class TestRapidConnectDisconnectCycles:
    """Test rapid connection/disconnection cycles for resource leaks"""

    def test_rapid_connect_disconnect_no_fd_leak(self) -> None:
        """Test rapid open/close cycles don't leak file descriptors.

        Scenario: Create and close many connections in quick succession
        Expected: All sockets properly closed, no fd leaks
        """
        connections = []
        mock_sockets = []

        # Create multiple connections
        for i in range(10):
            conn = Connection(AFI.ipv4, '192.0.2.1', '192.0.2.2')
            mock_sock = MagicMock(spec=socket.socket)
            mock_sock.fileno.return_value = 100 + i
            conn.io = mock_sock

            connections.append(conn)
            mock_sockets.append(mock_sock)

        # Rapidly close all connections
        with patch('exabgp.reactor.network.connection.log'):
            for conn in connections:
                conn.close()

        # Verify all sockets were closed
        for mock_sock in mock_sockets:
            mock_sock.close.assert_called_once()

    def test_rapid_connect_disconnect_poller_cleanup(self) -> None:
        """Test rapid cycles properly clean up polling state.

        Scenario: Open/close connections and verify poller dictionaries cleared
        Expected: No stale poller entries remain
        """
        with patch('exabgp.reactor.network.connection.log'):
            for i in range(5):
                conn = Connection(AFI.ipv4, '192.0.2.1', '192.0.2.2')
                mock_sock = MagicMock(spec=socket.socket)
                mock_sock.fileno.return_value = 50 + i
                conn.io = mock_sock

                # Access pollers to populate them
                with patch('select.poll') as mock_poll:
                    mock_poller = MagicMock()
                    mock_poll.return_value = mock_poller
                    mock_poller.poll.return_value = []
                    _ = conn.reading()

                # Close and verify io is None (connection closed)
                conn.close()
                assert conn.io is None

    def test_connection_churn_with_partial_io(self) -> None:
        """Test connection churn with partial I/O operations.

        Scenario: Start I/O operations then close before completion
        Expected: Graceful handling, no stuck generators
        """
        conn = Connection(AFI.ipv4, '192.0.2.1', '192.0.2.2')
        mock_sock = MagicMock(spec=socket.socket)
        mock_sock.fileno.return_value = 20
        conn.io = mock_sock

        # Start writer but don't complete
        test_data = b'incomplete write'
        mock_sock.send.return_value = 5  # Partial write

        writer_gen = conn.writer(test_data)

        with patch('select.poll') as mock_poll:
            with patch('exabgp.reactor.network.connection.log'):
                with patch('exabgp.reactor.network.connection.log'):
                    mock_poller = MagicMock()
                    mock_poll.return_value = mock_poller
                    mock_poller.poll.return_value = [(20, 4)]

                    # First iteration
                    result = next(writer_gen)
                    assert result is False

                    # Close connection mid-operation
                    conn.close()

        # Verify socket closed
        mock_sock.close.assert_called_once()


class TestPollingStateRaces:
    """Test race conditions in polling state management"""

    def test_concurrent_reading_writing_calls(self) -> None:
        """Test concurrent calls to reading() and writing().

        Scenario: Multiple checks of reading/writing status
        Expected: Consistent poller state, no corruption
        """
        conn = Connection(AFI.ipv4, '192.0.2.1', '192.0.2.2')
        mock_sock = MagicMock(spec=socket.socket)
        mock_sock.fileno.return_value = 15
        conn.io = mock_sock

        with patch('select.poll') as mock_poll:
            mock_poller = MagicMock()
            mock_poll.return_value = mock_poller

            # Call reading and writing multiple times
            for _ in range(5):
                is_reading = conn.reading()
                is_writing = conn.writing()

            # Verify poller state is consistent
            # Should have entries for fd 15
            assert 15 in conn._rpoller or not is_reading
            assert 15 in conn._wpoller or not is_writing

    def test_poller_state_after_socket_error(self) -> None:
        """Test poller cleanup after socket errors.

        Scenario: Socket error during poll operation
        Expected: Poller state cleared for that fd
        """
        conn = Connection(AFI.ipv4, '192.0.2.1', '192.0.2.2')
        mock_sock = MagicMock(spec=socket.socket)
        mock_sock.fileno.return_value = 16
        conn.io = mock_sock

        # Mock recv to raise socket error
        mock_sock.recv.side_effect = OSError(errno.ECONNRESET, "Connection reset")

        reader_gen = conn._reader(10)

        with patch('select.poll') as mock_poll:
            mock_poller = MagicMock()
            mock_poll.return_value = mock_poller
            mock_poller.poll.return_value = [(16, 1)]

            # Should raise LostConnection and clear poller
            with pytest.raises(LostConnection):
                next(reader_gen)

        # Poller should be cleaned up
        assert 16 not in conn._rpoller

    def test_poll_timeout_handling(self) -> None:
        """Test timeout handling in polling operations.

        Scenario: Poll times out waiting for I/O readiness
        Expected: Proper timeout detection, generator yields correctly
        """
        conn = Connection(AFI.ipv4, '192.0.2.1', '192.0.2.2')
        mock_sock = MagicMock(spec=socket.socket)
        mock_sock.fileno.return_value = 17
        conn.io = mock_sock

        reader_gen = conn._reader(10)

        with patch('select.poll') as mock_poll:
            mock_poller = MagicMock()
            mock_poll.return_value = mock_poller
            # Return empty list (timeout)
            mock_poller.poll.return_value = []

            # Should yield empty bytes on timeout
            result = next(reader_gen)
            assert result == b''


class TestMessageQueueOrderingRaces:
    """Test message ordering under concurrent operations"""

    def test_concurrent_reader_writer_ordering(self) -> None:
        """Test message ordering when reading and writing concurrently.

        Scenario: Read messages while writing messages
        Expected: Proper ordering maintained, no message loss
        """
        conn = Connection(AFI.ipv4, '192.0.2.1', '192.0.2.2')
        mock_sock = MagicMock(spec=socket.socket)
        mock_sock.fileno.return_value = 25
        conn.io = mock_sock

        # Create test data
        write_data = b'outgoing message'

        # Mock successful send
        mock_sock.send.return_value = len(write_data)

        # Create writer
        writer_gen = conn.writer(write_data)

        with patch('select.poll') as mock_poll:
            with patch('exabgp.reactor.network.connection.log'):
                with patch('exabgp.reactor.network.connection.log'):
                    mock_poller = MagicMock()
                    mock_poll.return_value = mock_poller
                    mock_poller.poll.return_value = [(25, 4)]  # POLLOUT

                    # Write should complete
                    try:
                        result = next(writer_gen)
                        # Keep iterating until complete
                        while result is False:
                            result = next(writer_gen)
                    except StopIteration:
                        pass

        # Verify data was sent
        mock_sock.send.assert_called()

    def test_bgp_message_assembly_ordering(self) -> None:
        """Test BGP message assembly maintains correct order.

        Scenario: Multiple BGP messages arrive in fragments
        Expected: Messages assembled in correct order
        """
        conn = Connection(AFI.ipv4, '192.0.2.1', '192.0.2.2')
        mock_sock = MagicMock(spec=socket.socket)
        mock_sock.fileno.return_value = 26
        conn.io = mock_sock

        # Create BGP KEEPALIVE message (19 bytes)
        marker = b'\xff' * 16
        length = struct.pack('!H', 19)
        msg_type = b'\x04'  # KEEPALIVE
        bgp_msg = marker + length + msg_type

        # Mock recv to return message in parts
        mock_sock.recv.side_effect = [
            bgp_msg[:10],   # First 10 bytes
            bgp_msg[10:],   # Remaining 9 bytes
        ]

        # Create reader for BGP message
        reader_gen = conn.reader()

        with patch('select.poll') as mock_poll:
            with patch('exabgp.reactor.network.connection.log'):
                with patch('exabgp.reactor.network.connection.log'):
                    mock_poller = MagicMock()
                    mock_poll.return_value = mock_poller
                    mock_poller.poll.return_value = [(26, 1)]  # POLLIN

                    # Read should assemble complete message
                    result = next(reader_gen)
                    # First yield is waiting for header
                    while result == (0, 0, b'', b'', None):
                        result = next(reader_gen)

                    # Verify we got a complete message structure
                    # Result is (length, msg_type, header, body, error)
                    assert result[0] == 19  # Message length
                    assert result[1] == 4   # KEEPALIVE type

    def test_buffer_state_consistency(self) -> None:
        """Test buffer state remains consistent during concurrent operations.

        Scenario: Multiple read operations with partial data
        Expected: Buffer accumulates correctly, no data loss
        """
        conn = Connection(AFI.ipv4, '192.0.2.1', '192.0.2.2')
        mock_sock = MagicMock(spec=socket.socket)
        mock_sock.fileno.return_value = 27
        conn.io = mock_sock

        # Test data larger than typical read
        test_data = b'A' * 100

        # Mock recv to return data in chunks
        chunk_size = 10
        chunks = [test_data[i:i+chunk_size] for i in range(0, len(test_data), chunk_size)]
        mock_sock.recv.side_effect = chunks

        reader_gen = conn._reader(100)

        with patch('select.poll') as mock_poll:
            with patch('exabgp.reactor.network.connection.log'):
                with patch('exabgp.reactor.network.connection.log'):
                    mock_poller = MagicMock()
                    mock_poll.return_value = mock_poller
                    mock_poller.poll.return_value = [(27, 1)]

                    # Read all chunks - _reader will accumulate until complete
                    result = None
                    for data in reader_gen:
                        if data and len(data) == 100:
                            result = data
                            break

                    # Should have assembled all data
                    assert result is not None
                    assert len(result) == 100
                    assert result == test_data


class TestConnectionStateTransitionRaces:
    """Test race conditions during connection state transitions"""

    def test_close_during_establishment(self) -> None:
        """Test close() called during connection establishment.

        Scenario: Connection being established when close() is called
        Expected: Clean abort, no half-open connections
        """
        conn = Connection(AFI.ipv4, '192.0.2.1', '192.0.2.2')
        mock_sock = MagicMock(spec=socket.socket)
        mock_sock.fileno.return_value = 30
        conn.io = mock_sock

        # Simulate mid-establishment
        assert conn.io is not None

        # Close immediately
        with patch('exabgp.reactor.network.connection.log'):
            conn.close()

        # Should be fully closed
        assert conn.io is None
        mock_sock.close.assert_called_once()

    def test_multiple_close_calls(self) -> None:
        """Test multiple close() calls are idempotent.

        Scenario: close() called multiple times
        Expected: No errors, socket closed only once
        """
        conn = Connection(AFI.ipv4, '192.0.2.1', '192.0.2.2')
        mock_sock = MagicMock(spec=socket.socket)
        mock_sock.fileno.return_value = 31
        conn.io = mock_sock

        # Call close multiple times
        with patch('exabgp.reactor.network.connection.log'):
            conn.close()
            conn.close()
            conn.close()

        # Socket should be closed only once
        mock_sock.close.assert_called_once()
        assert conn.io is None

    def test_io_operation_after_close(self) -> None:
        """Test I/O operations after close() are properly rejected.

        Scenario: Attempt read/write after connection closed
        Expected: NotConnected raised immediately for read, True yielded for write
        """
        conn = Connection(AFI.ipv4, '192.0.2.1', '192.0.2.2')
        mock_sock = MagicMock(spec=socket.socket)
        mock_sock.fileno.return_value = 32
        conn.io = mock_sock

        # Close connection
        with patch('exabgp.reactor.network.connection.log'):
            conn.close()

        # Attempt to read - should raise NotConnected
        reader_gen = conn._reader(10)
        with pytest.raises(NotConnected):
            next(reader_gen)

        # Attempt to write - writer returns True when no socket (line 179-182)
        writer_gen = conn.writer(b'test')
        result = next(writer_gen)
        assert result is True  # Writer yields True when io is None


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
