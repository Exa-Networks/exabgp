# encoding: utf-8
"""test_cli_transport.py

Unit tests for CLI transport selection (pipe vs Unix socket)
"""

import argparse
import os
import stat
from typing import Any
from unittest.mock import MagicMock, Mock, patch

import pytest

from exabgp.application.unixsocket import unix_socket


class TestUnixSocketDiscovery:
    """Test unix_socket() path discovery function"""

    def test_unix_socket_explicit_path(self) -> None:
        """Test unix_socket() with explicit exabgp_api_socketpath"""
        test_path = '/custom/path/to/exabgp.sock'

        with patch.dict(os.environ, {'exabgp_api_socketpath': test_path}):
            with patch('os.path.exists', return_value=True):
                with patch('os.stat') as mock_stat:
                    # Mock stat to return socket file type
                    mock_stat_result = Mock()
                    mock_stat_result.st_mode = stat.S_IFSOCK | 0o600
                    mock_stat.return_value = mock_stat_result

                    result = unix_socket('', 'exabgp')

                    # Should return the directory containing the socket
                    assert len(result) == 1
                    assert '/custom/path/to/' in result[0]

    def test_unix_socket_discovery_found(self) -> None:
        """Test unix_socket() finds socket in search locations"""

        def mock_stat_side_effect(path: str) -> Any:
            if path == '/run/exabgp/exabgp.sock':
                # Return a socket file
                mock_stat_result = Mock()
                mock_stat_result.st_mode = stat.S_IFSOCK | 0o600
                return mock_stat_result
            raise FileNotFoundError()

        with patch('os.path.exists', return_value=True):
            with patch('os.stat', side_effect=mock_stat_side_effect):
                result = unix_socket('', 'exabgp')

                # Should find socket in /run/exabgp/
                assert len(result) == 1
                assert result[0] == '/run/exabgp/'

    def test_unix_socket_discovery_not_found(self) -> None:
        """Test unix_socket() returns search paths when socket not found"""
        with patch('os.path.exists', return_value=False):
            with patch('os.stat', side_effect=FileNotFoundError()):
                result = unix_socket('', 'exabgp')

                # Should return list of search locations
                assert len(result) > 1
                assert '/run/exabgp/' in result
                assert '/var/run/exabgp/' in result

    def test_unix_socket_not_a_socket(self) -> None:
        """Test unix_socket() skips regular files"""

        def mock_stat_side_effect(path: str) -> Any:
            # Return a regular file, not a socket
            mock_stat_result = Mock()
            mock_stat_result.st_mode = stat.S_IFREG | 0o644  # Regular file
            return mock_stat_result

        with patch('os.path.exists', return_value=True):
            with patch('os.stat', side_effect=mock_stat_side_effect):
                result = unix_socket('', 'exabgp')

                # Should not find socket (returns search paths)
                assert len(result) > 1

    def test_unix_socket_custom_name(self) -> None:
        """Test unix_socket() with custom socket name"""

        def mock_stat_side_effect(path: str) -> Any:
            if path == '/run/exabgp/custom.sock':
                mock_stat_result = Mock()
                mock_stat_result.st_mode = stat.S_IFSOCK | 0o600
                return mock_stat_result
            raise FileNotFoundError()

        with patch('os.path.exists', return_value=True):
            with patch('os.stat', side_effect=mock_stat_side_effect):
                result = unix_socket('', 'custom')

                # Should find socket with custom name
                assert len(result) == 1
                assert result[0] == '/run/exabgp/'

    def test_unix_socket_with_root_prefix(self) -> None:
        """Test unix_socket() with root parameter"""

        def mock_stat_side_effect(path: str) -> Any:
            if path == '/custom/root/run/exabgp/exabgp.sock':
                mock_stat_result = Mock()
                mock_stat_result.st_mode = stat.S_IFSOCK | 0o600
                return mock_stat_result
            raise FileNotFoundError()

        with patch('os.path.exists', return_value=True):
            with patch('os.stat', side_effect=mock_stat_side_effect):
                result = unix_socket('/custom/root', 'exabgp')

                # Should find socket with root prefix
                assert len(result) == 1
                assert '/custom/root/run/exabgp/' in result[0]


class TestCLIArgumentParsing:
    """Test CLI argument parsing for transport selection"""

    def test_default_no_transport_flag(self) -> None:
        """Test argument parsing with no transport flags"""
        from exabgp.application.run import setargs

        parser = argparse.ArgumentParser()
        setargs(parser)

        # Parse with no transport flags
        args = parser.parse_args(['show', 'neighbor'])

        assert hasattr(args, 'use_pipe')
        assert hasattr(args, 'use_socket')
        assert args.use_pipe is False
        assert args.use_socket is False

    def test_pipe_flag(self) -> None:
        """Test argument parsing with --pipe flag"""
        from exabgp.application.run import setargs

        parser = argparse.ArgumentParser()
        setargs(parser)

        args = parser.parse_args(['--pipe', 'show', 'neighbor'])

        assert args.use_pipe is True
        assert args.use_socket is False

    def test_socket_flag(self) -> None:
        """Test argument parsing with --socket flag"""
        from exabgp.application.run import setargs

        parser = argparse.ArgumentParser()
        setargs(parser)

        args = parser.parse_args(['--socket', 'show', 'neighbor'])

        assert args.use_pipe is False
        assert args.use_socket is True

    def test_mutually_exclusive_flags(self) -> None:
        """Test that --pipe and --socket are mutually exclusive"""
        from exabgp.application.run import setargs

        parser = argparse.ArgumentParser()
        setargs(parser)

        # Should raise error when both flags provided
        with pytest.raises(SystemExit):
            parser.parse_args(['--pipe', '--socket', 'show', 'neighbor'])

    def test_pipename_flag(self) -> None:
        """Test --pipename flag still works"""
        from exabgp.application.run import setargs

        parser = argparse.ArgumentParser()
        setargs(parser)

        args = parser.parse_args(['--pipename', 'custom', 'show', 'neighbor'])

        assert args.pipename == 'custom'

    def test_pipename_with_pipe_flag(self) -> None:
        """Test --pipename works with --pipe flag"""
        from exabgp.application.run import setargs

        parser = argparse.ArgumentParser()
        setargs(parser)

        args = parser.parse_args(['--pipename', 'custom', '--pipe', 'show', 'neighbor'])

        assert args.pipename == 'custom'
        assert args.use_pipe is True


class TestTransportSelection:
    """Test transport selection logic in cmdline()"""

    def test_default_transport_is_socket(self) -> None:
        """Test that default transport is Unix socket"""
        # Create mock args with no flags
        mock_args = MagicMock()
        mock_args.use_pipe = False
        mock_args.use_socket = False
        mock_args.pipename = None
        mock_args.command = ['show', 'neighbor']

        with patch.dict(os.environ, {}, clear=True):
            with patch('exabgp.application.run.cmdline_socket') as mock_socket:
                with patch('exabgp.application.run.cmdline_pipe') as mock_pipe:
                    with patch('exabgp.application.run.getenv') as mock_getenv:
                        mock_env = MagicMock()
                        mock_env.api.pipename = 'exabgp'
                        mock_env.api.socketname = 'exabgp'
                        mock_getenv.return_value = mock_env

                        from exabgp.application.run import cmdline

                        try:
                            cmdline(mock_args)
                        except SystemExit:
                            pass

                        # Should call socket transport (default)
                        mock_socket.assert_called_once()
                        mock_pipe.assert_not_called()

    def test_pipe_flag_forces_pipe_transport(self) -> None:
        """Test --pipe flag forces pipe transport"""
        mock_args = MagicMock()
        mock_args.use_pipe = True
        mock_args.use_socket = False
        mock_args.pipename = None
        mock_args.command = ['show', 'neighbor']

        with patch.dict(os.environ, {}, clear=True):
            with patch('exabgp.application.run.cmdline_socket') as mock_socket:
                with patch('exabgp.application.run.cmdline_pipe') as mock_pipe:
                    with patch('exabgp.application.run.getenv') as mock_getenv:
                        mock_env = MagicMock()
                        mock_env.api.pipename = 'exabgp'
                        mock_getenv.return_value = mock_env

                        from exabgp.application.run import cmdline

                        try:
                            cmdline(mock_args)
                        except SystemExit:
                            pass

                        # Should call pipe transport
                        mock_pipe.assert_called_once()
                        mock_socket.assert_not_called()

    def test_socket_flag_forces_socket_transport(self) -> None:
        """Test --socket flag forces socket transport"""
        mock_args = MagicMock()
        mock_args.use_pipe = False
        mock_args.use_socket = True
        mock_args.pipename = None
        mock_args.command = ['show', 'neighbor']

        with patch.dict(os.environ, {}, clear=True):
            with patch('exabgp.application.run.cmdline_socket') as mock_socket:
                with patch('exabgp.application.run.cmdline_pipe') as mock_pipe:
                    with patch('exabgp.application.run.getenv') as mock_getenv:
                        mock_env = MagicMock()
                        mock_env.api.socketname = 'exabgp'
                        mock_getenv.return_value = mock_env

                        from exabgp.application.run import cmdline

                        try:
                            cmdline(mock_args)
                        except SystemExit:
                            pass

                        # Should call socket transport
                        mock_socket.assert_called_once()
                        mock_pipe.assert_not_called()

    def test_env_var_pipe_forces_pipe_transport(self) -> None:
        """Test exabgp_cli_transport=pipe environment variable"""
        mock_args = MagicMock()
        mock_args.use_pipe = False
        mock_args.use_socket = False
        mock_args.pipename = None
        mock_args.command = ['show', 'neighbor']

        with patch.dict(os.environ, {'exabgp_cli_transport': 'pipe'}):
            with patch('exabgp.application.run.cmdline_socket') as mock_socket:
                with patch('exabgp.application.run.cmdline_pipe') as mock_pipe:
                    with patch('exabgp.application.run.getenv') as mock_getenv:
                        mock_env = MagicMock()
                        mock_env.api.pipename = 'exabgp'
                        mock_getenv.return_value = mock_env

                        from exabgp.application.run import cmdline

                        try:
                            cmdline(mock_args)
                        except SystemExit:
                            pass

                        # Should call pipe transport
                        mock_pipe.assert_called_once()
                        mock_socket.assert_not_called()

    def test_env_var_socket_forces_socket_transport(self) -> None:
        """Test exabgp_cli_transport=socket environment variable"""
        mock_args = MagicMock()
        mock_args.use_pipe = False
        mock_args.use_socket = False
        mock_args.pipename = None
        mock_args.command = ['show', 'neighbor']

        with patch.dict(os.environ, {'exabgp_cli_transport': 'socket'}):
            with patch('exabgp.application.run.cmdline_socket') as mock_socket:
                with patch('exabgp.application.run.cmdline_pipe') as mock_pipe:
                    with patch('exabgp.application.run.getenv') as mock_getenv:
                        mock_env = MagicMock()
                        mock_env.api.socketname = 'exabgp'
                        mock_getenv.return_value = mock_env

                        from exabgp.application.run import cmdline

                        try:
                            cmdline(mock_args)
                        except SystemExit:
                            pass

                        # Should call socket transport
                        mock_socket.assert_called_once()
                        mock_pipe.assert_not_called()

    def test_flag_overrides_env_var(self) -> None:
        """Test command-line flag overrides environment variable"""
        mock_args = MagicMock()
        mock_args.use_pipe = True  # Flag says pipe
        mock_args.use_socket = False
        mock_args.pipename = None
        mock_args.command = ['show', 'neighbor']

        # Environment says socket
        with patch.dict(os.environ, {'exabgp_cli_transport': 'socket'}):
            with patch('exabgp.application.run.cmdline_socket') as mock_socket:
                with patch('exabgp.application.run.cmdline_pipe') as mock_pipe:
                    with patch('exabgp.application.run.getenv') as mock_getenv:
                        mock_env = MagicMock()
                        mock_env.api.pipename = 'exabgp'
                        mock_getenv.return_value = mock_env

                        from exabgp.application.run import cmdline

                        try:
                            cmdline(mock_args)
                        except SystemExit:
                            pass

                        # Flag should override env var - should use pipe
                        mock_pipe.assert_called_once()
                        mock_socket.assert_not_called()


class TestCommandShortcuts:
    """Test command nickname expansion"""

    def test_help_shortcut(self) -> None:
        """Test 'h' expands to 'help'"""
        mock_args = MagicMock()
        mock_args.use_pipe = False
        mock_args.use_socket = False
        mock_args.pipename = None
        mock_args.command = ['h']  # Should expand to 'help'

        with patch.dict(os.environ, {}, clear=True):
            with patch('exabgp.application.run.cmdline_socket') as mock_socket:
                with patch('exabgp.application.run.getenv') as mock_getenv:
                    mock_env = MagicMock()
                    mock_env.api.socketname = 'exabgp'
                    mock_getenv.return_value = mock_env

                    from exabgp.application.run import cmdline

                    try:
                        cmdline(mock_args)
                    except SystemExit:
                        pass

                    # Should be called with expanded 'help' command
                    mock_socket.assert_called_once()
                    call_args = mock_socket.call_args
                    # Second argument should be the command string
                    assert 'help' in call_args[0][1]

    def test_show_neighbor_shortcut(self) -> None:
        """Test 's n' expands to 'show neighbor'"""
        mock_args = MagicMock()
        mock_args.use_pipe = False
        mock_args.use_socket = False
        mock_args.pipename = None
        mock_args.command = ['s', 'n']  # Should expand to 'show neighbor'

        with patch.dict(os.environ, {}, clear=True):
            with patch('exabgp.application.run.cmdline_socket') as mock_socket:
                with patch('exabgp.application.run.getenv') as mock_getenv:
                    mock_env = MagicMock()
                    mock_env.api.socketname = 'exabgp'
                    mock_getenv.return_value = mock_env

                    from exabgp.application.run import cmdline

                    try:
                        cmdline(mock_args)
                    except SystemExit:
                        pass

                    mock_socket.assert_called_once()
                    call_args = mock_socket.call_args
                    # Should contain 'show neighbor'
                    assert 'show' in call_args[0][1]
                    assert 'neighbor' in call_args[0][1]


class TestResponseRouter:
    """Test ResponseRouter class for multi-client response routing (Fixes 1 & 2)"""

    def test_response_router_lock_initialization(self) -> None:
        """Test that ResponseRouter initializes with a lock (Fix 2)"""
        from exabgp.application.unixsocket import ResponseRouter

        router = ResponseRouter()

        assert hasattr(router, 'lock')
        assert router.active_command_client is None
        assert router.pending_requests == {}

    def test_set_active_client_thread_safe(self) -> None:
        """Test set_active_client uses lock (Fix 2)"""
        from exabgp.application.unixsocket import ResponseRouter

        router = ResponseRouter()
        router.set_active_client(42)

        assert router.active_command_client == 42

    def test_register_request(self) -> None:
        """Test request ID registration (Fix 1)"""
        from exabgp.application.unixsocket import ResponseRouter

        router = ResponseRouter()
        router.register_request('req-123', 42)

        assert router.pending_requests['req-123'] == 42

    def test_extract_request_id_text_format(self) -> None:
        """Test request ID extraction from text format (Fix 1)"""
        from exabgp.application.unixsocket import ResponseRouter

        router = ResponseRouter()

        # Text format: request_id=<id>
        request_id = router._extract_request_id('pong abc123 active=true request_id=req-456')
        assert request_id == 'req-456'

    def test_extract_request_id_json_format(self) -> None:
        """Test request ID extraction from JSON format (Fix 1)"""
        from exabgp.application.unixsocket import ResponseRouter

        router = ResponseRouter()

        # JSON format
        request_id = router._extract_request_id('{"pong": "abc123", "active": true, "request_id": "req-789"}')
        assert request_id == 'req-789'

    def test_extract_request_id_not_present(self) -> None:
        """Test request ID extraction returns None when not present"""
        from exabgp.application.unixsocket import ResponseRouter

        router = ResponseRouter()

        request_id = router._extract_request_id('pong abc123 active=true')
        assert request_id is None

    def test_classify_response_broadcast(self) -> None:
        """Test broadcast response classification"""
        from exabgp.application.unixsocket import ResponseRouter, ResponseType

        router = ResponseRouter()

        assert router.classify_response('neighbor 1.2.3.4 state established') == ResponseType.BROADCAST
        assert router.classify_response('neighbor 1.2.3.4 up') == ResponseType.BROADCAST
        assert router.classify_response('neighbor 1.2.3.4 down') == ResponseType.BROADCAST

    def test_classify_response_unicast(self) -> None:
        """Test unicast response classification"""
        from exabgp.application.unixsocket import ResponseRouter, ResponseType

        router = ResponseRouter()

        assert router.classify_response('done') == ResponseType.UNICAST
        assert router.classify_response('error') == ResponseType.UNICAST
        assert router.classify_response('pong abc123') == ResponseType.UNICAST

    def test_route_response_by_request_id(self) -> None:
        """Test response routing uses request_id when available (Fix 1)"""
        from exabgp.application.unixsocket import ResponseRouter, ClientConnection
        import socket as sock

        router = ResponseRouter()

        # Register a request
        router.register_request('req-123', 42)

        # Create mock clients
        mock_socket = Mock(spec=sock.socket)
        client42 = ClientConnection(socket=mock_socket, fd=42)
        client43 = ClientConnection(socket=mock_socket, fd=43)
        clients = {42: client42, 43: client43}

        # Route a response with request_id
        router.route_response(b'pong abc request_id=req-123\n', clients)

        # Should be routed to client 42 (by request_id)
        assert len(client42.write_queue) == 1
        assert len(client43.write_queue) == 0

    def test_route_response_clears_on_done(self) -> None:
        """Test response routing clears tracking on done/error"""
        from exabgp.application.unixsocket import ResponseRouter, ClientConnection
        import socket as sock

        router = ResponseRouter()

        # Setup active client
        router.set_active_client(42)

        # Create mock client
        mock_socket = Mock(spec=sock.socket)
        client42 = ClientConnection(socket=mock_socket, fd=42)
        clients = {42: client42}

        # Route 'done' response
        router.route_response(b'done\n', clients)

        # Active client should be cleared
        assert router.active_command_client is None


class TestPersistentConnectionRetry:
    """Test PersistentSocketConnection command retry functionality (Fix 3)"""

    def test_generate_request_id(self) -> None:
        """Test request ID generation is unique and sequential"""
        from exabgp.cli.persistent_connection import PersistentSocketConnection

        # Create connection without actually connecting
        with patch('socket.socket'):
            with patch.object(PersistentSocketConnection, '_connect'):
                with patch.object(PersistentSocketConnection, '_initial_ping'):
                    with patch.object(PersistentSocketConnection, '_setup_signal_handler'):
                        conn = PersistentSocketConnection('/fake/path')
                        conn.reader_thread = Mock()
                        conn.health_thread = Mock()

                        # Generate IDs
                        id1 = conn._generate_request_id()
                        id2 = conn._generate_request_id()
                        id3 = conn._generate_request_id()

                        # Should be sequential
                        assert id1 != id2 != id3
                        assert '-1' in id1
                        assert '-2' in id2
                        assert '-3' in id3

    def test_command_retry_flag_initialization(self) -> None:
        """Test command retry flags are initialized (Fix 3)"""
        from exabgp.cli.persistent_connection import PersistentSocketConnection

        with patch('socket.socket'):
            with patch.object(PersistentSocketConnection, '_connect'):
                with patch.object(PersistentSocketConnection, '_initial_ping'):
                    with patch.object(PersistentSocketConnection, '_setup_signal_handler'):
                        conn = PersistentSocketConnection('/fake/path')
                        conn.reader_thread = Mock()
                        conn.health_thread = Mock()

                        assert conn._last_command is None
                        assert conn._command_needs_retry is False
                        assert conn._request_id_counter == 0
