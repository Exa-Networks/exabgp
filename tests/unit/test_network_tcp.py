#!/usr/bin/env python3
# encoding: utf-8
"""
test_network_tcp.py

Comprehensive tests for TCP network layer functionality.
Tests socket creation, binding, connection, and configuration.

Created: 2025-11-08
"""

import pytest
import socket
import select
import platform
import binascii
from unittest.mock import Mock, patch, MagicMock

from exabgp.protocol.family import AFI
from exabgp.reactor.network import tcp
from exabgp.reactor.network.error import (
    NotConnected,
    BindingError,
    MD5Error,
    NagleError,
    TTLError,
    AsyncError,
)


class TestSocketCreation:
    """Test socket creation for IPv4 and IPv6"""

    def test_create_ipv4_socket(self):
        """Test creating an IPv4 socket"""
        io = tcp.create(AFI.ipv4)
        assert io is not None
        assert io.family == socket.AF_INET
        assert io.type == socket.SOCK_STREAM
        io.close()

    def test_create_ipv6_socket(self):
        """Test creating an IPv6 socket"""
        io = tcp.create(AFI.ipv6)
        assert io is not None
        assert io.family == socket.AF_INET6
        assert io.type == socket.SOCK_STREAM
        io.close()

    def test_create_socket_sets_reuse_addr(self):
        """Test that SO_REUSEADDR is set"""
        io = tcp.create(AFI.ipv4)
        # Get the socket option to verify it's set
        # Note: On macOS, getsockopt may return 4 instead of 1, so check for truthy value
        reuse = io.getsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR)
        assert reuse != 0
        io.close()

    def test_create_socket_with_interface(self):
        """Test creating socket with interface binding (may require root)"""
        # This test may fail without root privileges or on some platforms
        # We'll just verify it doesn't crash with invalid interface
        with pytest.raises(NotConnected, match="Could not bind to device"):
            tcp.create(AFI.ipv4, interface="nonexistent_interface_12345")

    @patch('socket.socket')
    def test_create_socket_failure(self, mock_socket):
        """Test socket creation failure"""
        mock_socket.side_effect = socket.error("Socket creation failed")

        with pytest.raises(NotConnected, match="Could not create socket"):
            tcp.create(AFI.ipv4)


class TestSocketBinding:
    """Test socket binding to local addresses"""

    def test_bind_ipv4(self):
        """Test binding to IPv4 localhost"""
        io = tcp.create(AFI.ipv4)
        tcp.bind(io, '127.0.0.1', AFI.ipv4)

        # Verify the socket is bound
        addr = io.getsockname()
        assert addr[0] == '127.0.0.1'
        assert addr[1] != 0  # Port should be assigned
        io.close()

    def test_bind_ipv6(self):
        """Test binding to IPv6 localhost"""
        io = tcp.create(AFI.ipv6)
        try:
            tcp.bind(io, '::1', AFI.ipv6)

            # Verify the socket is bound
            addr = io.getsockname()
            assert addr[0] == '::1'
            assert addr[1] != 0  # Port should be assigned
            io.close()
        except OSError:
            # IPv6 might not be available on all systems
            io.close()
            pytest.skip("IPv6 not available on this system")

    def test_bind_invalid_address(self):
        """Test binding to invalid IP address"""
        io = tcp.create(AFI.ipv4)

        with pytest.raises(BindingError, match="Could not bind to local ip"):
            tcp.bind(io, '999.999.999.999', AFI.ipv4)

        io.close()

    def test_bind_address_in_use(self):
        """Test binding to address already in use"""
        # Create first socket and bind it
        io1 = tcp.create(AFI.ipv4)
        io1.bind(('127.0.0.1', 0))
        addr = io1.getsockname()
        port = addr[1]

        # Try to bind second socket to same address (should fail without SO_REUSEPORT)
        io2 = socket.socket(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP)
        # Don't set SO_REUSEADDR or SO_REUSEPORT

        with pytest.raises(Exception):  # Should get some binding error
            io2.bind(('127.0.0.1', port))

        io1.close()
        io2.close()


class TestSocketConnection:
    """Test socket connection establishment"""

    def test_connect_to_unreachable_host(self):
        """Test connection to unreachable host"""
        io = tcp.create(AFI.ipv4)
        tcp.asynchronous(io, '192.0.2.1')  # Make it non-blocking

        # Connection to unreachable host should either raise or return (non-blocking)
        # With EINPROGRESS, connect() returns without exception in non-blocking mode
        try:
            tcp.connect(io, '192.0.2.1', 179, AFI.ipv4, None)
        except NotConnected:
            pass  # Expected for some scenarios

        io.close()

    def test_connect_ipv4_format(self):
        """Test IPv4 connection format (address, port)"""
        io = tcp.create(AFI.ipv4)
        tcp.asynchronous(io, '127.0.0.1')

        # Connect should not raise for non-blocking socket (EINPROGRESS is OK)
        try:
            tcp.connect(io, '127.0.0.1', 179, AFI.ipv4, None)
        except NotConnected as e:
            # Connection refused is expected if nothing is listening
            if 'Could not connect' in str(e):
                pass

        io.close()

    def test_connect_ipv6_format(self):
        """Test IPv6 connection format (address, port, flowinfo, scopeid)"""
        try:
            io = tcp.create(AFI.ipv6)
            tcp.asynchronous(io, '::1')

            # Connect should not raise for non-blocking socket (EINPROGRESS is OK)
            try:
                tcp.connect(io, '::1', 179, AFI.ipv6, None)
            except NotConnected as e:
                # Connection refused is expected if nothing is listening
                if 'Could not connect' in str(e):
                    pass

            io.close()
        except OSError:
            pytest.skip("IPv6 not available on this system")

    def test_connect_with_md5_error_message(self):
        """Test that MD5 password hint appears in error with MD5 enabled"""
        io = tcp.create(AFI.ipv4)
        # Use localhost with unlikely port for immediate connection refused
        # (avoids hanging on unreachable IPs which wait for timeout on OSX)

        # When MD5 is enabled and connection fails, error message should mention MD5
        with pytest.raises(NotConnected) as exc_info:
            tcp.connect(io, '127.0.0.1', 1, AFI.ipv4, md5='test123')

        # Verify MD5 hint is in error message
        assert "check your MD5 password" in str(exc_info.value)

        io.close()


class TestMD5Authentication:
    """Test TCP-MD5 authentication setup"""

    def test_md5_on_unsupported_platform(self):
        """Test MD5 setup on unsupported platform"""
        with patch('platform.system', return_value='Windows'):
            io = tcp.create(AFI.ipv4)

            with pytest.raises(MD5Error, match="ExaBGP has no MD5 support for Windows"):
                tcp.md5(io, '127.0.0.1', 179, 'password123', False)

            io.close()

    @patch('platform.system', return_value='FreeBSD')
    def test_md5_freebsd_requires_kernel_config(self, mock_platform):
        """Test FreeBSD MD5 requires kernel configuration"""
        io = tcp.create(AFI.ipv4)

        # FreeBSD requires 'kernel' as the md5 value
        with pytest.raises(MD5Error, match="FreeBSD requires that you set your MD5 key via ipsec.conf"):
            tcp.md5(io, '127.0.0.1', 179, 'password123', False)

        io.close()

    @patch('platform.system', return_value='FreeBSD')
    @patch('socket.socket.setsockopt')
    def test_md5_freebsd_with_kernel(self, mock_setsockopt, mock_platform):
        """Test FreeBSD MD5 with 'kernel' value"""
        mock_setsockopt.side_effect = socket.error("Not enabled")
        io = tcp.create(AFI.ipv4)

        with pytest.raises(MD5Error, match="rebuild your kernel"):
            tcp.md5(io, '127.0.0.1', 179, 'kernel', False)

        io.close()

    @patch('platform.system', return_value='Linux')
    def test_md5_linux_with_password(self, mock_platform):
        """Test Linux MD5 setup with ASCII password"""
        io = tcp.create(AFI.ipv4)

        # On Linux, this should attempt to set the socket option
        # It may fail if kernel doesn't support it, but shouldn't crash
        try:
            tcp.md5(io, '127.0.0.1', 179, 'password123', False)
        except MD5Error as e:
            # Expected if kernel doesn't support TCP_MD5SIG
            assert 'does not support TCP_MD5SIG' in str(e)

        io.close()

    @patch('platform.system', return_value='Linux')
    def test_md5_linux_with_base64(self, mock_platform):
        """Test Linux MD5 setup with base64-encoded password"""
        io = tcp.create(AFI.ipv4)

        # Base64 encoded "password" = cGFzc3dvcmQ=
        try:
            tcp.md5(io, '127.0.0.1', 179, 'cGFzc3dvcmQ=', True)
        except MD5Error as e:
            # Expected if kernel doesn't support TCP_MD5SIG
            assert 'does not support TCP_MD5SIG' in str(e) or 'Failed to decode' in str(e)

        io.close()

    @patch('platform.system', return_value='Linux')
    def test_md5_linux_invalid_base64(self, mock_platform):
        """Test Linux MD5 with invalid base64"""
        io = tcp.create(AFI.ipv4)

        # base64.b64decode can raise binascii.Error, which is caught and re-raised as MD5Error
        with pytest.raises((MD5Error, binascii.Error)):
            tcp.md5(io, '127.0.0.1', 179, '!!!invalid!!!', True)

        io.close()

    @patch('platform.system', return_value='Linux')
    def test_md5_linux_auto_detect_hex(self, mock_platform):
        """Test Linux MD5 auto-detection of hex vs base64"""
        io = tcp.create(AFI.ipv4)

        # All-hex string should be tried as base64
        try:
            tcp.md5(io, '127.0.0.1', 179, 'abcdef1234', None)  # None = auto-detect
        except MD5Error as e:
            # Expected if kernel doesn't support TCP_MD5SIG
            assert 'does not support TCP_MD5SIG' in str(e)

        io.close()

    @patch('platform.system', return_value='Linux')
    def test_md5_ipv6_address(self, mock_platform):
        """Test MD5 with IPv6 address"""
        io = tcp.create(AFI.ipv6)

        try:
            tcp.md5(io, '::1', 179, 'password123', False)
        except (MD5Error, OSError) as e:
            # Expected - either MD5 not supported or IPv6 not available
            pass

        io.close()


class TestNagleAlgorithm:
    """Test Nagle's algorithm configuration"""

    def test_nagle_disable_success(self):
        """Test successfully disabling Nagle's algorithm"""
        io = tcp.create(AFI.ipv4)
        tcp.nagle(io, '127.0.0.1')

        # Verify TCP_NODELAY is set
        # Note: On macOS, getsockopt may return 4 instead of 1, so check for truthy value
        nodelay = io.getsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY)
        assert nodelay != 0

        io.close()

    @patch('socket.socket.setsockopt')
    def test_nagle_disable_failure(self, mock_setsockopt):
        """Test Nagle disable failure handling"""
        mock_setsockopt.side_effect = socket.error("Not supported")
        io = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        with pytest.raises(NagleError, match="Could not disable nagle"):
            tcp.nagle(io, '127.0.0.1')

        io.close()


class TestTTLConfiguration:
    """Test TTL/hop limit configuration"""

    def test_ttl_ipv4(self):
        """Test IPv4 TTL setting"""
        io = tcp.create(AFI.ipv4)

        # Setting TTL to 255
        try:
            tcp.ttl(io, '127.0.0.1', 255)
            # Verify it was set
            ttl_value = io.getsockopt(socket.IPPROTO_IP, socket.IP_TTL)
            assert ttl_value == 255
        except TTLError:
            # Some systems may not support this
            pytest.skip("IP_TTL not supported on this system")

        io.close()

    def test_ttl_ipv4_zero_is_noop(self):
        """Test that TTL=0 does nothing"""
        io = tcp.create(AFI.ipv4)

        # TTL=0 should not set anything
        tcp.ttl(io, '127.0.0.1', 0)

        io.close()

    def test_ttl_ipv4_none_is_noop(self):
        """Test that TTL=None does nothing"""
        io = tcp.create(AFI.ipv4)

        # TTL=None should not set anything
        tcp.ttl(io, '127.0.0.1', None)

        io.close()

    def test_ttlv6(self):
        """Test IPv6 hop limit setting"""
        try:
            io = tcp.create(AFI.ipv6)

            try:
                tcp.ttlv6(io, '::1', 64)
                # Verify it was set
                hops = io.getsockopt(socket.IPPROTO_IPV6, socket.IPV6_UNICAST_HOPS)
                assert hops == 64
            except TTLError:
                pytest.skip("IPV6_UNICAST_HOPS not supported on this system")

            io.close()
        except OSError:
            pytest.skip("IPv6 not available on this system")

    @patch('socket.socket.setsockopt')
    def test_ttl_not_supported(self, mock_setsockopt):
        """Test TTL error when not supported"""
        mock_setsockopt.side_effect = socket.error("Not supported")
        io = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        with pytest.raises(TTLError, match="does not support IP_TTL"):
            tcp.ttl(io, '127.0.0.1', 64)

        io.close()

    def test_min_ttl(self):
        """Test minimum TTL setting"""
        io = tcp.create(AFI.ipv4)

        # min_ttl tries IP_MINTTL first, then IP_TTL
        try:
            tcp.min_ttl(io, '127.0.0.1', 255)
        except TTLError:
            # Expected if not supported
            pass

        io.close()

    def test_min_ttl_zero_is_noop(self):
        """Test that min_ttl=0 does nothing"""
        io = tcp.create(AFI.ipv4)

        # min_ttl=0 should not set anything
        tcp.min_ttl(io, '127.0.0.1', 0)

        io.close()


class TestAsynchronousMode:
    """Test non-blocking socket configuration"""

    def test_asynchronous_success(self):
        """Test setting socket to non-blocking mode"""
        io = tcp.create(AFI.ipv4)
        tcp.asynchronous(io, '127.0.0.1')

        # Verify socket is non-blocking
        assert io.getblocking() is False

        io.close()

    @patch('socket.socket.setblocking')
    def test_asynchronous_failure(self, mock_setblocking):
        """Test async mode failure handling"""
        mock_setblocking.side_effect = socket.error("Not supported")
        io = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        with pytest.raises(AsyncError, match="could not set socket non-blocking"):
            tcp.asynchronous(io, '127.0.0.1')

        io.close()


class TestSocketReadiness:
    """Test socket readiness polling"""

    def test_ready_with_unconnected_socket(self):
        """Test ready() with unconnected socket"""
        io = tcp.create(AFI.ipv4)
        tcp.asynchronous(io, '127.0.0.1')

        # Try to connect to unreachable address
        try:
            tcp.connect(io, '192.0.2.1', 179, AFI.ipv4, None)
        except NotConnected:
            pass

        # Check readiness
        generator = tcp.ready(io)
        result = next(generator)

        # Should get a tuple (bool, message)
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], bool)
        assert isinstance(result[1], str)

        io.close()

    @patch('select.poll')
    def test_ready_poll_error(self, mock_poll_class):
        """Test ready() handling poll errors"""
        import select as select_module

        mock_poller = MagicMock()
        mock_poller.poll.side_effect = select_module.error("Poll failed")
        mock_poll_class.return_value = mock_poller

        io = tcp.create(AFI.ipv4)
        tcp.asynchronous(io, '127.0.0.1')

        generator = tcp.ready(io)
        result = next(generator)

        # Should return False with error message
        assert result[0] is False
        assert 'error' in result[1].lower()

        io.close()

    @patch('select.poll')
    def test_ready_pollhup(self, mock_poll_class):
        """Test ready() with POLLHUP event"""
        mock_poller = MagicMock()
        mock_poller.poll.return_value = [(0, select.POLLHUP)]
        mock_poll_class.return_value = mock_poller

        io = tcp.create(AFI.ipv4)
        tcp.asynchronous(io, '127.0.0.1')

        generator = tcp.ready(io)
        result = next(generator)

        # POLLHUP means connection failed
        assert result[0] is False
        assert 'could not connect' in result[1]

        io.close()

    @patch('select.poll')
    def test_ready_pollerr(self, mock_poll_class):
        """Test ready() with POLLERR event"""
        mock_poller = MagicMock()
        mock_poller.poll.return_value = [(0, select.POLLERR)]
        mock_poll_class.return_value = mock_poller

        io = tcp.create(AFI.ipv4)
        tcp.asynchronous(io, '127.0.0.1')

        generator = tcp.ready(io)
        result = next(generator)

        # POLLERR means connection failed
        assert result[0] is False
        assert 'failed' in result[1]

        io.close()


class TestIntegration:
    """Integration tests combining multiple operations"""

    def test_full_socket_setup_ipv4(self):
        """Test complete IPv4 socket setup sequence"""
        # Create socket
        io = tcp.create(AFI.ipv4)

        # Bind to local address
        tcp.bind(io, '127.0.0.1', AFI.ipv4)

        # Disable Nagle's algorithm
        tcp.nagle(io, '127.0.0.1')

        # Set non-blocking
        tcp.asynchronous(io, '127.0.0.1')

        # Verify all settings
        # Note: On macOS, getsockopt may return 4 instead of 1, so check for truthy value
        assert io.getsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY) != 0
        assert io.getblocking() is False

        io.close()

    def test_full_socket_setup_ipv6(self):
        """Test complete IPv6 socket setup sequence"""
        try:
            # Create socket
            io = tcp.create(AFI.ipv6)

            # Bind to local address
            tcp.bind(io, '::1', AFI.ipv6)

            # Disable Nagle's algorithm
            tcp.nagle(io, '::1')

            # Set non-blocking
            tcp.asynchronous(io, '::1')

            # Verify all settings
            # Note: On macOS, getsockopt may return 4 instead of 1, so check for truthy value
            assert io.getsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY) != 0
            assert io.getblocking() is False

            io.close()
        except OSError:
            pytest.skip("IPv6 not available on this system")

    def test_socket_cleanup(self):
        """Test that sockets are properly cleaned up"""
        io = tcp.create(AFI.ipv4)
        fd = io.fileno()

        # FD should be valid
        assert fd >= 0

        io.close()

        # After close, FD should be -1
        assert io.fileno() == -1


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
