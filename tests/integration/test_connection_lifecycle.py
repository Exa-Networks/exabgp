#!/usr/bin/env python3
# encoding: utf-8
"""test_connection_lifecycle.py

Integration tests for full connection lifecycle with real socket mocks.
Tests complete BGP connection scenarios including socket creation, connection
establishment, message exchange, and teardown using real socket pairs.

Created: 2025-11-08
"""

import os
import socket
import struct
import threading
import time
from typing import Any, Generator
from unittest.mock import Mock, patch

import pytest

# Set up environment before importing ExaBGP modules
os.environ['exabgp_log_enable'] = 'false'
os.environ['exabgp_log_level'] = 'CRITICAL'


@pytest.fixture(autouse=True)
def mock_logger() -> Generator[None, None, None]:
    """Mock the logger to avoid initialization issues."""
    from exabgp.logger.option import option

    original_logger = option.logger
    original_formater = option.formater

    mock_option_logger = Mock()
    mock_option_logger.debug = Mock()
    mock_option_logger.info = Mock()
    mock_option_logger.warning = Mock()
    mock_option_logger.error = Mock()
    mock_option_logger.critical = Mock()

    mock_formater = Mock(return_value="formatted message")

    option.logger = mock_option_logger
    option.formater = mock_formater

    yield

    option.logger = original_logger
    option.formater = original_formater


from exabgp.bgp.message import Message  # noqa: E402
from exabgp.protocol.family import AFI  # noqa: E402
from exabgp.reactor.network import tcp  # noqa: E402
from exabgp.reactor.network.error import LostConnection, NotConnected  # noqa: E402
from exabgp.reactor.network.incoming import Incoming  # noqa: E402
from exabgp.reactor.network.outgoing import Outgoing  # noqa: E402


class MockBGPServer:
    """Mock BGP server for integration testing.
    Creates a real TCP server socket that can accept connections and exchange BGP messages.
    """

    def __init__(self, host: Any ='127.0.0.1', port: Any =0, afi: Any =AFI.ipv4):
        self.host = host
        self.port = port
        self.afi = afi
        self.server_socket = None
        self.client_socket = None
        self.server_thread = None
        self.running = False
        self.accept_connections = True
        self.messages_to_send = []
        self.messages_received = []
        self.connection_established = False

    def start(self) -> None:
        """Start the mock BGP server in a background thread"""
        family = socket.AF_INET if self.afi == AFI.ipv4 else socket.AF_INET6
        self.server_socket = socket.socket(family, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        if self.afi == AFI.ipv4:
            self.server_socket.bind((self.host, self.port))
        else:
            self.server_socket.bind((self.host, self.port, 0, 0))

        # Get the actual port assigned
        self.port = self.server_socket.getsockname()[1]

        self.server_socket.listen(1)
        self.server_socket.settimeout(5.0)  # 5 second timeout
        self.running = True

        self.server_thread = threading.Thread(target=self._server_loop, daemon=True)
        self.server_thread.start()

        # Wait a bit for the server to be ready
        time.sleep(0.1)

    def _server_loop(self):
        """Server loop that accepts connections and handles messages"""
        try:
            if self.accept_connections:
                self.client_socket, addr = self.server_socket.accept()
                self.client_socket.settimeout(2.0)
                self.connection_established = True

                # Handle message exchange
                while self.running:
                    # Try to receive a message
                    try:
                        header = self.client_socket.recv(19)
                        if not header:
                            break
                        if len(header) == 19:
                            self.messages_received.append(header)

                            # Parse length and read body if needed
                            length = struct.unpack('!H', header[16:18])[0]
                            if length > 19:
                                body = self.client_socket.recv(length - 19)
                                self.messages_received[-1] += body
                    except socket.timeout:
                        pass
                    except Exception:
                        break

                    # Send queued messages
                    while self.messages_to_send:
                        msg = self.messages_to_send.pop(0)
                        try:
                            self.client_socket.sendall(msg)
                        except Exception:
                            break

                    time.sleep(0.01)
        except socket.timeout:
            pass
        except Exception:
            pass
        finally:
            if self.client_socket:
                try:
                    self.client_socket.close()
                except Exception:
                    pass

    def queue_message(self, message: Any) -> None:
        """Queue a message to be sent to the client"""
        self.messages_to_send.append(message)

    def stop(self) -> None:
        """Stop the server and clean up"""
        self.running = False
        if self.server_thread:
            self.server_thread.join(timeout=1.0)
        if self.client_socket:
            try:
                self.client_socket.close()
            except Exception:
                pass
        if self.server_socket:
            try:
                self.server_socket.close()
            except Exception:
                pass


def create_bgp_message(msg_type: Any, body: Any =b'') -> Any:
    """Create a valid BGP message.

    Args:
        msg_type: BGP message type (1=OPEN, 2=UPDATE, 3=NOTIFICATION, 4=KEEPALIVE, 5=ROUTE-REFRESH)
        body: Message body bytes

    Returns:
        Complete BGP message with marker, length, type, and body
    """
    marker = Message.MARKER
    length = 19 + len(body)
    header = marker + struct.pack('!H', length) + bytes([msg_type])
    return header + body


def create_open_message(asn: Any =64512, router_id: Any ='192.0.2.1', hold_time: Any =180) -> Any:
    """Create a BGP OPEN message.

    Args:
        asn: Autonomous System Number
        router_id: Router ID as string (IPv4 address format)
        hold_time: Hold time in seconds

    Returns:
        Complete OPEN message bytes
    """
    # Parse router ID
    router_id_bytes = socket.inet_aton(router_id)

    # BGP version (4) + ASN (2 bytes) + Hold Time (2 bytes) + Router ID (4 bytes) + Opt Param Len (1 byte)
    body = struct.pack('!BHH4sB', 4, asn, hold_time, router_id_bytes, 0)

    return create_bgp_message(1, body)


def create_keepalive_message() -> Any:
    """Create a BGP KEEPALIVE message"""
    return create_bgp_message(4, b'')


def create_notification_message(error_code: Any =1, error_subcode: Any =1, data: Any =b'') -> Any:
    """Create a BGP NOTIFICATION message"""
    body = struct.pack('!BB', error_code, error_subcode) + data
    return create_bgp_message(3, body)


class TestConnectionLifecycleBasics:
    """Test basic connection lifecycle operations with real sockets"""

    def test_socket_pair_communication(self) -> None:
        """Test basic socket pair communication (sanity check)"""
        # Create a socket pair
        if hasattr(socket, 'socketpair'):
            client, server = socket.socketpair()
        else:
            # Fallback for systems without socketpair
            pytest.skip("socketpair not available")

        try:
            # Send data from client to server
            client.send(b'test')
            data = server.recv(4)
            assert data == b'test'

            # Send data from server to client
            server.send(b'response')
            data = client.recv(8)
            assert data == b'response'
        finally:
            client.close()
            server.close()

    def test_connection_with_real_server_socket(self) -> None:
        """Test Connection can work with a real server socket"""
        server = MockBGPServer()
        server.start()

        try:
            # Create a client socket and connect
            client_sock = tcp.create(AFI.ipv4)
            tcp.asynchronous(client_sock, server.host)

            # Connect to the mock server
            try:
                tcp.connect(client_sock, server.host, server.port, AFI.ipv4, None)
            except NotConnected:
                # Non-blocking connect may raise EINPROGRESS, which is OK
                pass

            # Wait for connection to establish
            time.sleep(0.2)

            # Check if server received the connection
            assert server.connection_established

            client_sock.close()
        finally:
            server.stop()


class TestOutgoingConnectionLifecycle:
    """Test Outgoing connection lifecycle with real sockets"""

    @pytest.mark.timeout(10)
    def test_outgoing_connection_establishment(self) -> None:
        """Test Outgoing connection can establish with a real server"""
        server = MockBGPServer()
        server.start()

        try:
            # Create outgoing connection
            outgoing = Outgoing(AFI.ipv4, server.host, '127.0.0.1', port=server.port)

            # Attempt to establish connection
            established = False
            attempts = 0
            for result in outgoing.establish():
                if result:
                    established = True
                    break
                attempts += 1
                if attempts > 50:  # Prevent infinite loop
                    break
                time.sleep(0.1)

            assert established, "Connection should establish"
            assert outgoing.io is not None, "Socket should be assigned"

            # Wait for server thread to accept the connection (race condition fix)
            server_accepted = False
            for _ in range(20):  # Wait up to 2 seconds
                if server.connection_established:
                    server_accepted = True
                    break
                time.sleep(0.1)

            assert server_accepted, "Server should receive connection"

            outgoing.close()
        finally:
            server.stop()

    @pytest.mark.timeout(10)
    def test_outgoing_send_keepalive(self) -> None:
        """Test Outgoing can send KEEPALIVE message"""
        server = MockBGPServer()
        server.start()

        try:
            # Create and establish outgoing connection
            outgoing = Outgoing(AFI.ipv4, server.host, '127.0.0.1', port=server.port)

            established = False
            for result in outgoing.establish():
                if result:
                    established = True
                    break
                time.sleep(0.1)

            assert established

            # Send KEEPALIVE message
            keepalive = create_keepalive_message()
            for sent in outgoing.writer(keepalive):
                if sent:
                    break

            # Wait for server to receive it
            time.sleep(0.2)

            assert len(server.messages_received) > 0, "Server should receive message"
            assert server.messages_received[0] == keepalive, "Should receive KEEPALIVE"

            outgoing.close()
        finally:
            server.stop()

    @pytest.mark.timeout(10)
    def test_outgoing_receive_keepalive(self) -> None:
        """Test Outgoing can receive KEEPALIVE message"""
        server = MockBGPServer()
        server.start()

        try:
            # Create and establish outgoing connection
            outgoing = Outgoing(AFI.ipv4, server.host, '127.0.0.1', port=server.port)

            established = False
            for result in outgoing.establish():
                if result:
                    established = True
                    break
                time.sleep(0.1)

            assert established

            # Queue a KEEPALIVE from server to client
            keepalive = create_keepalive_message()
            server.queue_message(keepalive)

            # Wait for message to be sent
            time.sleep(0.2)

            # Read the message
            reader = outgoing.reader()
            length, msg_type, header, body, error = next(reader)

            # Skip waiting states
            while length == 0 and error is None:
                length, msg_type, header, body, error = next(reader)

            assert error is None, "Should not have error"
            assert length == 19, "KEEPALIVE is 19 bytes"
            assert msg_type == 4, "Should be KEEPALIVE (type 4)"

            outgoing.close()
        finally:
            server.stop()

    @pytest.mark.timeout(10)
    def test_outgoing_full_message_exchange(self) -> None:
        """Test full bidirectional message exchange"""
        server = MockBGPServer()
        server.start()

        try:
            # Create and establish outgoing connection
            outgoing = Outgoing(AFI.ipv4, server.host, '127.0.0.1', port=server.port)

            established = False
            for result in outgoing.establish():
                if result:
                    established = True
                    break
                time.sleep(0.1)

            assert established

            # 1. Send OPEN message
            open_msg = create_open_message(asn=64512, router_id='192.0.2.2')
            for sent in outgoing.writer(open_msg):
                if sent:
                    break

            time.sleep(0.1)

            # 2. Server sends OPEN response
            server_open = create_open_message(asn=64513, router_id='192.0.2.1')
            server.queue_message(server_open)

            time.sleep(0.2)

            # 3. Receive server OPEN
            reader = outgoing.reader()
            length, msg_type, header, body, error = next(reader)
            while length == 0 and error is None:
                length, msg_type, header, body, error = next(reader)

            assert error is None
            assert msg_type == 1, "Should receive OPEN (type 1)"

            # 4. Exchange KEEPALIVES
            keepalive = create_keepalive_message()
            for sent in outgoing.writer(keepalive):
                if sent:
                    break

            server.queue_message(keepalive)
            time.sleep(0.1)

            # 5. Receive KEEPALIVE
            reader = outgoing.reader()
            length, msg_type, header, body, error = next(reader)
            while length == 0 and error is None:
                length, msg_type, header, body, error = next(reader)

            assert error is None
            assert msg_type == 4, "Should receive KEEPALIVE (type 4)"

            # Verify server received our messages
            assert len(server.messages_received) >= 2, "Server should receive OPEN and KEEPALIVE"

            outgoing.close()
        finally:
            server.stop()


class TestIncomingConnectionLifecycle:
    """Test Incoming connection lifecycle with real sockets"""

    def test_incoming_connection_from_real_socket(self) -> None:
        """Test Incoming can be created from a real connected socket"""
        # Create a socket pair to simulate an accepted connection
        if not hasattr(socket, 'socketpair'):
            pytest.skip("socketpair not available")

        server_sock, client_sock = socket.socketpair()

        try:
            # Mock nagle to avoid issues with socketpair
            with patch('exabgp.reactor.network.incoming.nagle'):
                # Create Incoming connection with the server side socket
                incoming = Incoming(AFI.ipv4, '192.0.2.1', '127.0.0.1', server_sock)

                assert incoming.io is not None
                assert incoming.io == server_sock
                assert incoming.peer == '192.0.2.1'
                assert incoming.local == '127.0.0.1'

                incoming.close()
        finally:
            try:
                client_sock.close()
            except Exception:
                pass

    def test_incoming_receive_message(self) -> None:
        """Test Incoming can receive messages from connected socket"""
        if not hasattr(socket, 'socketpair'):
            pytest.skip("socketpair not available")

        server_sock, client_sock = socket.socketpair()

        try:
            # Mock nagle to avoid issues with socketpair
            with patch('exabgp.reactor.network.incoming.nagle'):
                # Create Incoming connection
                incoming = Incoming(AFI.ipv4, '192.0.2.1', '127.0.0.1', server_sock)

                # Client sends KEEPALIVE
                keepalive = create_keepalive_message()
                client_sock.sendall(keepalive)

                # Wait for data to arrive
                time.sleep(0.1)

                # Read the message
                reader = incoming.reader()
                length, msg_type, header, body, error = next(reader)

                # Skip waiting states
                while length == 0 and error is None:
                    length, msg_type, header, body, error = next(reader)

                assert error is None
                assert length == 19
                assert msg_type == 4

                incoming.close()
        finally:
            try:
                client_sock.close()
            except Exception:
                pass

    def test_incoming_send_message(self) -> None:
        """Test Incoming can send messages to connected socket"""
        if not hasattr(socket, 'socketpair'):
            pytest.skip("socketpair not available")

        server_sock, client_sock = socket.socketpair()

        try:
            # Mock nagle to avoid issues with socketpair
            with patch('exabgp.reactor.network.incoming.nagle'):
                # Create Incoming connection
                incoming = Incoming(AFI.ipv4, '192.0.2.1', '127.0.0.1', server_sock)

                # Send KEEPALIVE from Incoming
                keepalive = create_keepalive_message()
                for sent in incoming.writer(keepalive):
                    if sent:
                        break

                # Client receives the message
                time.sleep(0.1)
                data = client_sock.recv(19)

                assert len(data) == 19
                assert data == keepalive

                incoming.close()
        finally:
            try:
                client_sock.close()
            except Exception:
                pass


class TestConnectionErrorScenarios:
    """Test connection error and edge case scenarios"""

    def test_connection_to_unreachable_host(self) -> None:
        """Test connection attempt to unreachable host"""
        # Use TEST-NET-1 (192.0.2.0/24) which should be unreachable
        outgoing = Outgoing(AFI.ipv4, '192.0.2.254', '127.0.0.1', port=179)

        # Should not establish
        established = False
        attempts = 0
        for result in outgoing.establish():
            if result:
                established = True
                break
            attempts += 1
            if attempts > 5:  # Just try a few times
                break

        # Should not establish to unreachable host
        assert not established

    def test_connection_close_during_read(self) -> None:
        """Test handling of connection close during read operation"""
        if not hasattr(socket, 'socketpair'):
            pytest.skip("socketpair not available")

        server_sock, client_sock = socket.socketpair()
        incoming = None

        try:
            # Mock nagle to avoid issues with socketpair
            with patch('exabgp.reactor.network.incoming.nagle'):
                # Create Incoming connection
                incoming = Incoming(AFI.ipv4, '192.0.2.1', '127.0.0.1', server_sock)

                # Start reading (will wait for data)
                reader = incoming.reader()

                # Close the client socket
                client_sock.close()

                # Try to read - should raise LostConnection
                with pytest.raises(LostConnection):
                    for _ in range(10):
                        next(reader)
                        time.sleep(0.1)

        finally:
            if incoming:
                incoming.close()

    def test_invalid_bgp_marker(self) -> None:
        """Test detection of invalid BGP marker"""
        if not hasattr(socket, 'socketpair'):
            pytest.skip("socketpair not available")

        server_sock, client_sock = socket.socketpair()
        incoming = None

        try:
            # Mock nagle to avoid issues with socketpair
            with patch('exabgp.reactor.network.incoming.nagle'):
                # Create Incoming connection
                incoming = Incoming(AFI.ipv4, '192.0.2.1', '127.0.0.1', server_sock)

                # Send message with invalid marker
                invalid_msg = b'\x00' * 16 + struct.pack('!H', 19) + b'\x04'
                client_sock.sendall(invalid_msg)

                time.sleep(0.1)

                # Read should detect error
                reader = incoming.reader()
                length, msg_type, header, body, error = next(reader)

                while length == 0 and error is None:
                    length, msg_type, header, body, error = next(reader)

                # Should have a NotifyError
                from exabgp.reactor.network.error import NotifyError
                assert isinstance(error, NotifyError)
                assert error.code == 1  # Message Header Error
                assert error.subcode == 1  # Connection Not Synchronized

        finally:
            if incoming:
                incoming.close()
            try:
                client_sock.close()
            except Exception:
                pass


class TestConnectionConcurrency:
    """Test concurrent read/write operations"""

    @pytest.mark.timeout(10)
    def test_concurrent_read_write(self) -> None:
        """Test simultaneous read and write operations"""
        server = MockBGPServer()
        server.start()

        try:
            # Create and establish outgoing connection
            outgoing = Outgoing(AFI.ipv4, server.host, '127.0.0.1', port=server.port)

            established = False
            for result in outgoing.establish():
                if result:
                    established = True
                    break
                time.sleep(0.1)

            assert established

            # Queue messages from server
            for _ in range(3):
                server.queue_message(create_keepalive_message())

            # Simultaneously send and receive
            messages_sent = 0
            messages_received = 0

            for i in range(10):
                # Try to send
                if messages_sent < 3:
                    keepalive = create_keepalive_message()
                    for sent in outgoing.writer(keepalive):
                        if sent:
                            messages_sent += 1
                            break
                        time.sleep(0.01)

                # Try to receive
                if messages_received < 3:
                    reader = outgoing.reader()
                    length, msg_type, header, body, error = next(reader)
                    if length > 0:
                        messages_received += 1

                time.sleep(0.1)

            # Should have sent and received messages
            assert messages_sent > 0, "Should send messages"
            assert messages_received > 0, "Should receive messages"

            outgoing.close()
        finally:
            server.stop()


class TestConnectionStateManagement:
    """Test connection state management and cleanup"""

    def test_connection_cleanup_on_close(self) -> None:
        """Test proper cleanup when connection is closed"""
        server = MockBGPServer()
        server.start()

        try:
            # Create and establish connection
            outgoing = Outgoing(AFI.ipv4, server.host, '127.0.0.1', port=server.port)

            established = False
            for result in outgoing.establish():
                if result:
                    established = True
                    break
                time.sleep(0.1)

            assert established
            assert outgoing.io is not None

            # Close the connection
            outgoing.close()

            # Socket should be closed
            assert outgoing.io is None

        finally:
            server.stop()

    def test_multiple_close_calls(self) -> None:
        """Test that multiple close() calls don't cause errors"""
        server = MockBGPServer()
        server.start()

        try:
            # Create and establish connection
            outgoing = Outgoing(AFI.ipv4, server.host, '127.0.0.1', port=server.port)

            established = False
            for result in outgoing.establish():
                if result:
                    established = True
                    break
                time.sleep(0.1)

            assert established

            # Close multiple times - should not raise
            outgoing.close()
            outgoing.close()
            outgoing.close()

            assert outgoing.io is None

        finally:
            server.stop()

    def test_file_descriptor_tracking(self) -> None:
        """Test file descriptor is properly tracked"""
        server = MockBGPServer()
        server.start()

        try:
            # Create connection
            outgoing = Outgoing(AFI.ipv4, server.host, '127.0.0.1', port=server.port)

            # Before connection, fd should be -1
            assert outgoing.fd() == -1

            # Establish connection
            established = False
            for result in outgoing.establish():
                if result:
                    established = True
                    break
                time.sleep(0.1)

            assert established

            # After connection, fd should be valid
            assert outgoing.fd() >= 0

            # After close, fd should be -1
            outgoing.close()
            assert outgoing.fd() == -1

        finally:
            server.stop()


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--timeout=30'])
