# encoding: utf-8
"""test_cli_transport.py

Unit tests for CLI transport selection (pipe vs Unix socket)
"""

import argparse
import contextlib
import io
import os
import signal
import stat
import threading
from collections.abc import Iterator
from queue import Empty, Queue
from typing import Any
from unittest.mock import Mock, patch

import pytest

from exabgp.application.unixsocket import unix_socket
from exabgp.environment import getenv


def stat_of(mode: int) -> os.stat_result:
    """A real stat result with only st_mode set, as os.stat returns one."""
    return os.stat_result((mode, 0, 0, 0, 0, 0, 0, 0, 0, 0))


# Names no daemon on the test machine uses, so each transport fails to find its endpoint
# and says which endpoint it was looking for.
UNUSED_PIPE = 'exabgp-unit-test-no-such-pipe'
UNUSED_SOCKET = 'exabgp-unit-test-no-such-socket'


def run_cmdline(
    capsys: pytest.CaptureFixture[str],
    command: list[str],
    environ: dict[str, str],
    use_pipe: bool = False,
    use_socket: bool = False,
) -> str:
    """Run `exabgp run` against no daemon and return what it printed.

    The transports are not replaced (a compiled module calls its own functions directly):
    each one reports, by name, the endpoint it could not find, which says which one ran.
    """
    from exabgp.application.run import cmdline

    arguments = argparse.Namespace(use_pipe=use_pipe, use_socket=use_socket, pipename=UNUSED_PIPE, command=command)
    api = getenv().api
    socketname = api.socketname
    api.socketname = UNUSED_SOCKET
    try:
        with patch.dict(os.environ, environ, clear=True), pytest.raises(SystemExit) as exited:
            cmdline(arguments)
    finally:
        api.socketname = socketname
    assert exited.value.code == 1
    return capsys.readouterr().out


def used_pipe(output: str) -> bool:
    return f"could not find ExaBGP's named pipes ({UNUSED_PIPE}.in" in output


def used_socket(output: str) -> bool:
    return f"could not find ExaBGP's Unix socket ({UNUSED_SOCKET}.sock)" in output


class TestUnixSocketDiscovery:
    """Test unix_socket() path discovery function"""

    def test_unix_socket_explicit_path(self) -> None:
        """Test unix_socket() with explicit exabgp_api_socketpath"""
        test_path = '/custom/path/to/exabgp.sock'

        with patch.dict(os.environ, {'exabgp_api_socketpath': test_path}):
            with patch('os.path.exists', return_value=True):
                with patch('os.stat', return_value=stat_of(stat.S_IFSOCK | 0o600)):
                    result = unix_socket('', 'exabgp')

                    # Should return the directory containing the socket
                    assert len(result) == 1
                    assert '/custom/path/to/' in result[0]

    def test_unix_socket_discovery_found(self) -> None:
        """Test unix_socket() finds socket in search locations"""

        def mock_stat_side_effect(path: str) -> Any:
            if path == '/run/exabgp/exabgp.sock':
                # Return a socket file
                return stat_of(stat.S_IFSOCK | 0o600)
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
            return stat_of(stat.S_IFREG | 0o644)

        with patch('os.path.exists', return_value=True):
            with patch('os.stat', side_effect=mock_stat_side_effect):
                result = unix_socket('', 'exabgp')

                # Should not find socket (returns search paths)
                assert len(result) > 1

    def test_unix_socket_custom_name(self) -> None:
        """Test unix_socket() with custom socket name"""

        def mock_stat_side_effect(path: str) -> Any:
            if path == '/run/exabgp/custom.sock':
                return stat_of(stat.S_IFSOCK | 0o600)
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
                return stat_of(stat.S_IFSOCK | 0o600)
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

    def test_default_transport_is_socket(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Test that default transport is Unix socket"""
        output = run_cmdline(capsys, ['show', 'neighbor'], {})
        assert used_socket(output)
        assert not used_pipe(output)

    def test_pipe_flag_forces_pipe_transport(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Test --pipe flag forces pipe transport"""
        output = run_cmdline(capsys, ['show', 'neighbor'], {}, use_pipe=True)
        assert used_pipe(output)
        assert not used_socket(output)

    def test_socket_flag_forces_socket_transport(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Test --socket flag forces socket transport"""
        output = run_cmdline(capsys, ['show', 'neighbor'], {'exabgp_cli_transport': 'pipe'}, use_socket=True)
        assert used_socket(output)
        assert not used_pipe(output)

    def test_env_var_pipe_forces_pipe_transport(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Test exabgp_cli_transport=pipe environment variable"""
        output = run_cmdline(capsys, ['show', 'neighbor'], {'exabgp_cli_transport': 'pipe'})
        assert used_pipe(output)
        assert not used_socket(output)

    def test_env_var_socket_forces_socket_transport(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Test exabgp_cli_transport=socket environment variable"""
        output = run_cmdline(capsys, ['show', 'neighbor'], {'exabgp_cli_transport': 'socket'})
        assert used_socket(output)
        assert not used_pipe(output)

    def test_flag_overrides_env_var(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Test command-line flag overrides environment variable"""
        # Environment says socket, the flag says pipe
        output = run_cmdline(capsys, ['show', 'neighbor'], {'exabgp_cli_transport': 'socket'}, use_pipe=True)
        assert used_pipe(output)
        assert not used_socket(output)


class TestCommandShortcuts:
    """Test command nickname expansion"""

    def test_help_shortcut(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Test 'h' expands to 'help'"""
        output = run_cmdline(capsys, ['h'], {})
        # The expanded command is shown before it is sent
        assert 'command: help\n' in output
        assert used_socket(output)

    def test_show_neighbor_shortcut(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Test 's n' expands to 'show neighbor'"""
        output = run_cmdline(capsys, ['s', 'n'], {})
        assert 'command: show neighbor\n' in output
        assert used_socket(output)


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


class FakeDaemonSocket:
    """A unix socket to a daemon which answers a ping, and records what the client sends."""

    made: list['FakeDaemonSocket'] = []

    def __init__(self, *args: object) -> None:
        self.replies = [b'{"pong": "daemon-uuid-one", "active": true}\ndone\n']
        self.sent: list[bytes] = []
        self.closed = False
        FakeDaemonSocket.made.append(self)

    def connect(self, path: str) -> None:
        return None

    def settimeout(self, timeout: float) -> None:
        return None

    def sendall(self, data: bytes) -> None:
        self.sent.append(data)

    def recv(self, size: int) -> bytes:
        return self.replies.pop(0) if self.replies else b''

    def close(self) -> None:
        self.closed = True


class IdleThread(threading.Thread):
    """A thread which is never started, so no background loop runs during the test."""

    def start(self) -> None:
        return None


class ImpatientQueue(Queue[str]):
    """A response queue which times out at once rather than after the real five seconds."""

    def get(self, block: bool = True, timeout: float | None = None) -> str:
        raise Empty


@contextlib.contextmanager
def fake_daemon() -> Iterator[list[FakeDaemonSocket]]:
    """Every socket the connection opens talks to a fake daemon; no thread runs, no handler is left.

    The class's own methods are not patched: a compiled class calls them directly, so the
    collaborators they reach (the socket, the thread, the signal module) are replaced instead.
    """
    FakeDaemonSocket.made = []
    previous_handler = signal.getsignal(signal.SIGUSR1)
    try:
        with (
            patch('socket.socket', FakeDaemonSocket),
            patch('threading.Thread', IdleThread),
            contextlib.redirect_stderr(io.StringIO()),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            yield FakeDaemonSocket.made
    finally:
        signal.signal(signal.SIGUSR1, previous_handler)


class TestPersistentConnectionRetry:
    """Test PersistentSocketConnection command retry functionality (Fix 3)"""

    def test_generate_request_id(self) -> None:
        """Test request ID generation is unique and sequential"""
        from exabgp.cli.persistent_connection import PersistentSocketConnection

        with fake_daemon():
            conn = PersistentSocketConnection('/fake/path')

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

        with fake_daemon():
            conn = PersistentSocketConnection('/fake/path')

        assert conn._last_command is None
        assert conn._command_needs_retry is False
        assert conn._request_id_counter == 0

    def test_reconnect_resends_without_waiting_on_reader_queue(self) -> None:
        from exabgp.cli.persistent_connection import PersistentSocketConnection

        with fake_daemon() as sockets:
            connection = PersistentSocketConnection('/fake/path')
            connection.command_in_progress = True
            connection.pending_user_command = True
            connection._command_needs_retry = True
            connection._last_command = 'show neighbor'

            with patch('readline.get_line_buffer', return_value=''):
                assert connection._reconnect(max_attempts=1, retry_delay=0) is True

        old_socket, new_socket = sockets
        assert old_socket.closed
        # The new socket carries the ping of the reconnection, then the command resent as is.
        assert new_socket.sent[1:] == [b'show neighbor\n']
        # send_command() would have waited on the queue this reader thread fills, and cleared
        # the flag when nothing arrived: the resend went straight to the socket.
        assert connection._command_needs_retry is True
        assert connection.pending_responses.empty()

    def test_send_command_timeout_clears_the_retry_flag(self) -> None:
        """Nothing waits on a command which has already timed out.

        The flag is cleared only when a response arrives, so a command that timed out
        stayed marked for retry. The next reconnect then resent it: the daemon ran it a
        second time, unasked, and its reply arrived with no caller to receive it, to be
        flushed as a stale response by whichever command came next.
        """
        from exabgp.cli.persistent_connection import PersistentSocketConnection

        with fake_daemon():
            connection = PersistentSocketConnection('/fake/path')

        # Time out at once rather than waiting out the real five second deadline.
        connection.pending_responses = ImpatientQueue()

        response = connection.send_command('show neighbor')

        assert 'Timeout' in response
        assert connection._command_needs_retry is False
