#!/usr/bin/env python3
# encoding: utf-8
"""test_connection_simple.py

Simplified tests for network connection layer functionality.
Tests core connection behaviors without complex generator mocking.

Created: 2025-11-08
"""

import pytest
import os

# Set up environment before importing ExaBGP modules
os.environ['exabgp_log_enable'] = 'false'
os.environ['exabgp_log_level'] = 'CRITICAL'

from exabgp.protocol.family import AFI
from exabgp.reactor.network.connection import Connection
from exabgp.bgp.message.open.capability.extended import ExtendedMessage
from unittest.mock import Mock


class TestConnectionBasics:
    """Test basic Connection functionality"""

    def test_create_ipv4_connection(self) -> None:
        """Test creating an IPv4 connection"""
        conn = Connection(AFI.ipv4, '192.0.2.1', '192.0.2.2')

        assert conn.afi == AFI.ipv4
        assert conn.peer == '192.0.2.1'
        assert conn.local == '192.0.2.2'
        assert conn.io is None
        assert conn.established is False

    def test_create_ipv6_connection(self) -> None:
        """Test creating an IPv6 connection"""
        conn = Connection(AFI.ipv6, '2001:db8::1', '2001:db8::2')

        assert conn.afi == AFI.ipv6
        assert conn.peer == '2001:db8::1'
        assert conn.local == '2001:db8::2'

    def test_initial_message_size(self) -> None:
        """Test default message size"""
        conn = Connection(AFI.ipv4, '192.0.2.1', '192.0.2.2')

        assert conn.msg_size == ExtendedMessage.INITIAL_SIZE

    def test_name_includes_addresses(self) -> None:
        """Test connection name contains addresses"""
        conn = Connection(AFI.ipv4, '192.0.2.1', '192.0.2.2')
        name = conn.name()

        assert '192.0.2.1' in name
        assert '192.0.2.2' in name

    def test_session_identifier(self) -> None:
        """Test session identifier format"""
        conn = Connection(AFI.ipv4, '192.0.2.1', '192.0.2.2')
        session = conn.session()

        # Should contain direction and ID
        assert '-' in session

    def test_fd_without_socket(self) -> None:
        """Test fd() returns -1 when no socket"""
        conn = Connection(AFI.ipv4, '192.0.2.1', '192.0.2.2')

        assert conn.fd() == -1

    def test_fd_with_socket(self) -> None:
        """Test fd() returns file descriptor with socket"""
        conn = Connection(AFI.ipv4, '192.0.2.1', '192.0.2.2')

        mock_sock = Mock()
        mock_sock.fileno.return_value = 42
        conn.io = mock_sock

        assert conn.fd() == 42
        mock_sock.fileno.assert_called_once()

    def test_success_increments_identifier(self) -> None:
        """Test success() increments connection identifier"""
        conn = Connection(AFI.ipv4, '192.0.2.1', '192.0.2.2')

        initial_id = conn.id
        new_id = conn.success()

        assert new_id == initial_id + 1
        assert Connection.identifier.get(conn.direction) == new_id

    def test_close_without_socket(self) -> None:
        """Test close() when no socket exists"""
        conn = Connection(AFI.ipv4, '192.0.2.1', '192.0.2.2')

        # Should not raise
        conn.close()
        assert conn.io is None

    def test_close_with_socket(self) -> None:
        """Test close() handles socket cleanup"""
        from unittest.mock import patch
        conn = Connection(AFI.ipv4, '192.0.2.1', '192.0.2.2')

        mock_sock = Mock()
        conn.io = mock_sock

        # Mock the logger to allow close to proceed
        with patch('exabgp.reactor.network.connection.log'):
            conn.close()
            mock_sock.close.assert_called_once()

        assert conn.io is None

    def test_close_handles_exception(self) -> None:
        """Test close() handles exceptions gracefully"""
        from unittest.mock import patch
        conn = Connection(AFI.ipv4, '192.0.2.1', '192.0.2.2')

        mock_sock = Mock()
        mock_sock.close.side_effect = Exception("Close failed")
        conn.io = mock_sock

        # Should not raise, just set io to None
        with patch('exabgp.reactor.network.connection.log'):
            conn.close()
        assert conn.io is None

    def test_del_calls_close(self) -> None:
        """Test __del__ calls close()"""
        from unittest.mock import patch
        conn = Connection(AFI.ipv4, '192.0.2.1', '192.0.2.2')

        mock_sock = Mock()
        conn.io = mock_sock

        # Mock the logger to allow close to proceed
        with patch('exabgp.reactor.network.connection.log'):
            # Call __del__
            conn.__del__()
            mock_sock.close.assert_called_once()

        assert conn.io is None

    def test_defensive_mode_initialized(self) -> None:
        """Test defensive mode is initialized from environment"""
        conn = Connection(AFI.ipv4, '192.0.2.1', '192.0.2.2')

        # Should have defensive attribute
        assert hasattr(conn, 'defensive')
        # Since we disabled logging, it should be False
        assert conn.defensive is False


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
