"""socket.py

Unix socket-based CLI control process for ExaBGP.
Similar to pipe.py but uses Unix domain sockets instead of named pipes.

Created: 2025-11-19
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import os
import sys
import stat
import json
import signal
import select
import socket
import traceback
import contextlib
import re
import time
import threading
from collections import deque

from exabgp.util.backlog import Backlog
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable

from exabgp.reactor.network.error import error

kb = 1024
mb = kb * 1024

# a single API command must fit in one line, and the backlog is what we could not forward yet
MAX_COMMAND_SIZE = mb


def command_too_large(pending: bytes, limit: int = MAX_COMMAND_SIZE) -> bool:
    """Whether what has been read can never be dispatched and must stop growing.

    A command is dispatched on its newline, so bytes with no newline in them are a command
    still arriving.  If they pass the limit, no newline is coming.

    A function, so a test can hand it bytes: the check it replaced was tested by reading
    this file as text and asserting the constant's name appeared in it.
    """
    return b'\n' not in pending and len(pending) > limit


MAX_BACKLOG_SIZE = 100 * mb

# what a turned away client may have sent, read and dropped before closing it, and for how long
TURN_AWAY_DRAIN_SIZE = 64 * kb
TURN_AWAY_DRAIN_SECONDS = 0.2


class ResponseType(Enum):
    """Type of response from ExaBGP reactor."""

    UNICAST = 'unicast'  # Response to specific client command
    BROADCAST = 'broadcast'  # Event broadcast to all clients


@dataclass
class ClientConnection:
    """Track individual CLI client connection."""

    socket: socket.socket
    fd: int
    write_queue: deque[bytes] = field(default_factory=deque)
    connected_at: float = 0.0

    def __post_init__(self) -> None:
        if self.connected_at == 0.0:
            self.connected_at = time.time()


class ResponseRouter:
    """Route responses to appropriate client(s).

    Thread-safe response routing with request ID tracking.
    - Fix 1: Request IDs allow correlating responses to specific client commands
    - Fix 2: Lock protects active_command_client from race conditions
    """

    def __init__(self) -> None:
        self.active_command_client: int | None = None  # fd of client executing command
        self.lock = threading.Lock()  # Fix 2: Protect active_command_client
        # Fix 1: Track pending requests by request_id -> client_fd
        self.pending_requests: dict[str, int] = {}

    def register_request(self, request_id: str, client_fd: int) -> None:
        """Register a pending request with its client fd (Fix 1)."""
        with self.lock:
            self.pending_requests[request_id] = client_fd

    def set_active_client(self, client_fd: int) -> None:
        """Set the active command client (Fix 2: thread-safe)."""
        with self.lock:
            self.active_command_client = client_fd

    def _extract_request_id(self, line: str) -> str | None:
        """Extract request_id from response if present (Fix 1).

        Supports formats:
        - Text: "pong <uuid> active=true request_id=<id>"
        - JSON: {"pong": ..., "request_id": "<id>"}
        - General: any response with request_id=<id> suffix
        """
        # Check for request_id= in text format
        if 'request_id=' in line:
            match = re.search(r'request_id=(\S+)', line)
            if match:
                return match.group(1)

        # A line which opens with a brace but does not parse is a plain text response which
        # happens to start that way. It carries no request_id, and that is what we return.
        if line.startswith('{'):
            with contextlib.suppress(json.JSONDecodeError, ValueError):
                parsed = json.loads(line)
                if isinstance(parsed, dict) and 'request_id' in parsed:
                    return str(parsed['request_id'])

        return None

    def classify_response(self, line: str) -> ResponseType:
        """Determine if response is unicast or broadcast."""
        stripped = line.strip()

        # Terminators always unicast to requesting client
        if stripped in ('done', 'error'):
            return ResponseType.UNICAST

        # Broadcast patterns (events from reactor)
        broadcast_patterns = [
            r'^neighbor \S+ state ',
            r'^neighbor \S+ up$',
            r'^neighbor \S+ down$',
            r'^neighbor \S+ connected$',
            r'^neighbor \S+ closing$',
            r'^neighbor \S+ announced ',
            r'^neighbor \S+ withdrawn ',
            r'^neighbor \S+ received ',
            r'^neighbor \S+ operational ',
        ]

        for pattern in broadcast_patterns:
            if re.match(pattern, line):
                return ResponseType.BROADCAST

        # Default: unicast (command response)
        return ResponseType.UNICAST

    def route_response(self, line: bytes, clients: dict[int, ClientConnection]) -> None:
        """Route response to appropriate client(s).

        Fix 1: First try to route by request_id if present.
        Fix 2: Use lock when accessing active_command_client.
        """
        line_str = line.decode('utf-8', errors='replace')
        response_type = self.classify_response(line_str)

        if response_type == ResponseType.BROADCAST:
            # Send to ALL clients
            for client in clients.values():
                client.write_queue.append(line)
        else:
            # Fix 1: Try to route by request_id first
            request_id = self._extract_request_id(line_str)
            target_client: int | None = None

            with self.lock:
                if request_id and request_id in self.pending_requests:
                    target_client = self.pending_requests[request_id]
                elif self.active_command_client:
                    target_client = self.active_command_client

                # Route to target client
                if target_client and target_client in clients:
                    clients[target_client].write_queue.append(line)

                    # Clear tracking after done/error
                    stripped = line_str.strip()
                    if stripped in ('done', 'error'):
                        # Clear request_id tracking
                        if request_id and request_id in self.pending_requests:
                            del self.pending_requests[request_id]
                        # Clear active client
                        if self.active_command_client == target_client:
                            self.active_command_client = None


def unix_socket(root: str, socketname: str = 'exabgp') -> list[str]:
    """Discover Unix socket path for CLI communication.

    Searches standard locations for socket file.
    Returns [location] if found, or list of search locations if not found.
    """
    locations = [
        '/run/exabgp/',
        f'/run/{os.getuid()}/',
        '/run/',
        '/var/run/exabgp/',
        f'/var/run/{os.getuid()}/',
        '/var/run/',
        root + '/run/exabgp/',
        root + f'/run/{os.getuid()}/',
        root + '/run/',
        root + '/var/run/exabgp/',
        root + f'/var/run/{os.getuid()}/',
        root + '/var/run/',
    ]

    # Check for explicit path override
    explicit_path = os.environ.get('exabgp_api_socketpath', '')
    if explicit_path:
        if os.path.exists(explicit_path):
            try:
                if stat.S_ISSOCK(os.stat(explicit_path).st_mode):
                    os.environ['exabgp_cli_socket'] = os.path.dirname(explicit_path) + '/'
                    return [os.path.dirname(explicit_path) + '/']
            except OSError as exc:
                # The operator named this socket, and what follows ignores it and searches the
                # standard locations, where it can find another daemon's socket and connect to
                # it as if nothing had happened.
                sys.stderr.write(f'warning: cannot use exabgp_api_socketpath {explicit_path}: {exc}\n')
                sys.stderr.flush()

    for location in locations:
        socket_path = location + socketname + '.sock'
        try:
            if stat.S_ISSOCK(os.stat(socket_path).st_mode):
                os.environ['exabgp_cli_socket'] = location
                return [location]
        except OSError:
            continue

    return locations


def env(app: str, section: str, name: str, default: str) -> str:
    """Get environment variable with fallback."""
    r = os.environ.get(f'{app}.{section}.{name}', None)
    if r is None:
        r = os.environ.get(f'{app}_{section}_{name}', None)
    if r is None:
        return default
    return r


class Control:
    """Unix socket server for CLI control.

    Creates a Unix domain socket server that forwards messages between:
    - Unix socket (CLI commands) <-> stdout (to ExaBGP)
    - stdin (from ExaBGP) <-> Unix socket (responses to CLI)
    """

    terminating = False

    def __init__(self, location: str) -> None:
        # Check for explicit socket path override
        explicit_path = os.environ.get('exabgp_api_socketpath', '')
        if explicit_path:
            self.socket_path = explicit_path
        else:
            socketname = env('exabgp', 'api', 'socketname', 'exabgp')
            self.socket_path = location + socketname + '.sock'

        self.server_socket: socket.socket | None = None

        # Multi-client support configuration
        multi_client_str = env('exabgp', 'api', 'multi_client', 'false').lower()
        self.multi_client_mode = multi_client_str in ('true', '1', 'yes')
        self.max_clients = int(env('exabgp', 'api', 'max_clients', '10'))

        # Multi-client tracking
        self.clients: dict[int, ClientConnection] = {}  # fd -> ClientConnection
        self.response_router = ResponseRouter()

        # Legacy single-client tracking (for backward compatibility)
        self.client_socket: socket.socket | None = None
        self.client_fd: int | None = None

        # The daemon's end: its commands go out on stdout, its answers come in on stdin
        self._stdin = 0
        self._stdout = 1

        # What loop() reads from each descriptor, where it forwards it, and what it holds
        self._read: dict[int, Callable[[int], bytes]] = {}
        self._write: dict[int, Callable[[bytes], int] | None] = {}
        self._backlog: dict[int, Backlog] = {}
        self._store: dict[int, bytes] = {}

    def init(self) -> bool:
        """Initialize socket server."""
        # Remove stale socket file if it exists
        try:
            if os.path.exists(self.socket_path):
                # Check if it's actually a socket
                if stat.S_ISSOCK(os.stat(self.socket_path).st_mode):
                    # Try to connect to see if it's still active
                    test_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                    try:
                        test_sock.connect(self.socket_path)
                        test_sock.close()
                        sys.stdout.write(
                            f'error: socket already exists and is active ({os.path.abspath(self.socket_path)})\n'
                        )
                        sys.stdout.flush()
                        return False
                    except socket.error:
                        # Socket exists but nothing is listening - it's stale, remove it
                        os.unlink(self.socket_path)
                else:
                    sys.stdout.write(
                        f'error: a file exists which is not a socket ({os.path.abspath(self.socket_path)})\n'
                    )
                    sys.stdout.flush()
                    return False
        except OSError as exc:
            sys.stdout.write(f'error: could not check socket file {os.path.abspath(self.socket_path)}: {exc}\n')
            sys.stdout.flush()
            return False

        # Create directory if it doesn't exist
        socket_dir = os.path.dirname(self.socket_path)
        if socket_dir and not os.path.exists(socket_dir):
            try:
                os.makedirs(socket_dir, mode=0o700, exist_ok=True)
                # mode= is filtered by the umask: exabgp's default of 0o137 left 0o600, a
                # directory nobody can enter, and binding the socket inside it then failed
                os.chmod(socket_dir, 0o700)
                sys.stdout.write(f'created socket directory: {socket_dir}\n')
                sys.stdout.flush()
            except OSError as exc:
                sys.stdout.write(f'error: could not create socket directory {socket_dir}: {exc}\n')
                sys.stdout.flush()
                return False

        # Create Unix domain socket
        try:
            self.server_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self.server_socket.bind(self.socket_path)
            # Use higher backlog for multi-client mode
            backlog = self.max_clients if self.multi_client_mode else 1
            self.server_socket.listen(backlog)
            self.server_socket.setblocking(False)
        except OSError as exc:
            sys.stdout.write(f'error: could not create socket {os.path.abspath(self.socket_path)}: {exc}\n')
            sys.stdout.flush()
            return False

        signal.signal(signal.SIGINT, self.terminate)
        signal.signal(signal.SIGTERM, self.terminate)
        return True

    def _disconnect_client(self, fd: int) -> None:
        """Disconnect a specific client (multi-client mode).

        The daemon is not told: it keeps no list of clients, and the 'done' answering a
        'bye' would be routed to whichever client asked last, as the end of its command.
        """
        if fd not in self.clients:
            return

        client = self.clients[fd]

        # A close which fails is a socket the client has already torn down, which is the state
        # closing it was meant to reach.
        with contextlib.suppress(OSError):
            client.socket.close()

        # Remove from tracking
        del self.clients[fd]

        # Fix 2: Clear active command client if it was this client (thread-safe)
        with self.response_router.lock:
            if self.response_router.active_command_client == fd:
                self.response_router.active_command_client = None
            # Also clear any pending requests for this client
            stale_requests = [rid for rid, cfd in self.response_router.pending_requests.items() if cfd == fd]
            for rid in stale_requests:
                del self.response_router.pending_requests[rid]

    def cleanup_client(self) -> None:
        """Clean up client connection only (keep server listening).

        Note: Only closes the socket, not clearing client_fd.
        The main loop will detect this state and clean up data structures.
        """
        if self.client_socket:
            # A close which fails is a socket the client has already torn down, which is the
            # state closing it was meant to reach.
            with contextlib.suppress(OSError):
                self.client_socket.close()
            self.client_socket = None
            # Do NOT clear client_fd here - main loop needs it to clean up dicts

    def cleanup(self) -> None:
        """Clean up all resources (server shutdown)."""
        # Disconnect all clients
        for fd in list(self.clients.keys()):
            self._disconnect_client(fd)

        # Legacy cleanup
        self.cleanup_client()
        self.client_fd = None  # Full cleanup includes clearing fd

        if self.server_socket:
            # We are shutting down, so a listening socket which refuses to close is already in
            # the state we want it in.
            with contextlib.suppress(OSError):
                self.server_socket.close()
            self.server_socket = None

        # Remove socket file
        try:
            if os.path.exists(self.socket_path):
                os.unlink(self.socket_path)
        except OSError as exc:
            # The socket file outlives us, and the next start has to connect to it to prove it
            # is stale before it can bind its own.
            sys.stderr.write(f'cannot remove the socket file {os.path.abspath(self.socket_path)}: {exc}\n')
            sys.stderr.flush()

    def terminate(self, signum: int | None = None, frame: object = None) -> None:
        """Signal handler for clean shutdown."""
        if self.terminating:
            sys.exit(1)
        self.terminating = True
        self.cleanup()
        sys.exit(0)

    @staticmethod
    def _turn_away(new_socket: socket.socket, message: bytes) -> None:
        """Tell a client we cannot serve why, then close it."""
        try:
            new_socket.setblocking(True)
            new_socket.sendall(message)
            # A client which has already hung up cannot be half closed, and the close below
            # is all we wanted from it.
            with contextlib.suppress(OSError):
                new_socket.shutdown(socket.SHUT_WR)
            Control._drain(new_socket)
            new_socket.close()
        except OSError:
            # The rejection could not be delivered, so dropping the connection has to say it
            # instead.
            with contextlib.suppress(OSError):
                new_socket.close()

    @staticmethod
    def _drain(new_socket: socket.socket) -> None:
        """Read and drop what the client sent, until it hangs up, briefly.

        On Linux, closing a unix socket with unread data in it resets the connection: the
        client, reading the refusal, got ECONNRESET instead of the end of the stream.
        """
        deadline = time.monotonic() + TURN_AWAY_DRAIN_SECONDS
        drained = 0
        with contextlib.suppress(OSError, ValueError):
            while drained < TURN_AWAY_DRAIN_SIZE:
                # ValueError: settimeout refuses the negative time left once the deadline passed
                new_socket.settimeout(deadline - time.monotonic())
                data = new_socket.recv(TURN_AWAY_DRAIN_SIZE)
                if not data:
                    return
                drained += len(data)

    def read_on(self, reading: list[int | None]) -> list[int]:
        """Poll file descriptors for readable data."""
        sleep_time = 1000  # 1 second timeout

        poller = select.poll()
        for io in reading:
            if io is not None:
                poller.register(io, select.POLLIN | select.POLLPRI | select.POLLHUP | select.POLLNVAL | select.POLLERR)

        ready = []
        for io, event in poller.poll(sleep_time):
            if event & select.POLLIN or event & select.POLLPRI:
                ready.append(io)
            elif event & select.POLLHUP or event & select.POLLERR or event & select.POLLNVAL:
                # Connection closed or error
                if io == self.client_fd:
                    # Client disconnected - close socket but add to ready so main loop cleans up
                    self.cleanup_client()
                    ready.append(io)  # Add to ready so main loop can clean up data structures
                else:
                    # stdin/server socket issue
                    sys.exit(1)
        return ready

    def _grow(self, source: int, chunk: bytes) -> None:
        """store only grows here, so the cap is only checked here.

        It used to be checked in the first branch of _consume() alone, and the three
        drains below appended to store without it.
        """
        self._store[source] += chunk
        if command_too_large(self._store[source]):
            sys.stderr.write('received a command larger than %d bytes - exiting\n' % MAX_COMMAND_SIZE)
            sys.stderr.flush()
            sys.exit(1)

    def _forget(self, fd: int) -> None:
        """Drop the buffers of a client which has gone."""
        self._read.pop(fd, None)
        self._write.pop(fd, None)
        self._backlog.pop(fd, None)
        self._store.pop(fd, None)

    def _consume(self, source: int) -> None:
        if not self._backlog[source] and b'\n' not in self._store[source]:
            self._grow(source, self._read[source](1024))
        else:
            self._backlog[source].append(self._read[source](1024))
            # Memory limit check, on the bytes queued and not on the number of sources
            if self._backlog[source].nbytes + len(self._store[source]) > MAX_BACKLOG_SIZE:
                sys.stderr.write('using too much memory - exiting\n')
                sys.stderr.flush()
                sys.exit(1)

    def _enable_ack(self) -> None:
        """Enable ACK for this CLI control process (v6 API format)."""
        try:
            os.write(self._stdout, b'session ack enable\n')
            # Read and discard the 'done' response
            poller = select.poll()
            poller.register(self._stdin, select.POLLIN)
            if poller.poll(1000):
                response = b''
                while b'\n' not in response:
                    chunk = os.read(self._stdin, 1024)
                    if not chunk:
                        break
                    response += chunk
        except OSError as exc:
            # Without the acknowledgement the reactor stops sending 'done', and every CLI
            # client on this socket waits out its timeout on every command it sends.
            sys.stderr.write(f'cannot enable API acknowledgements: {exc}\n')
            sys.stderr.flush()

    def _std_reader(self, number: int) -> bytes:
        try:
            return os.read(self._stdin, number)
        except OSError as exc:
            if exc.errno in error.block:
                return b''
            sys.exit(1)

    def _std_writer(self, line: bytes) -> int:
        try:
            return os.write(self._stdout, line)
        except OSError as exc:
            if exc.errno in error.block:
                return 0
            sys.exit(1)

    def _socket_reader(self, number: int) -> bytes:
        if not self.client_socket:
            return b''
        try:
            data = self.client_socket.recv(number)
            if not data:
                # Empty read means client closed connection (EOF)
                self.cleanup_client()
            return data
        except OSError as exc:
            if exc.errno in error.block:
                return b''
            # Client disconnected with error
            self.cleanup_client()
            return b''

    def _socket_writer(self, line: bytes) -> int:
        if not self.client_socket:
            return 0
        try:
            return self.client_socket.send(line)
        except OSError as exc:
            if exc.errno in error.block:
                return 0
            # Client disconnected
            self.cleanup_client()
            return 0

    def _client_reader(self, client_fd: int) -> Callable[[int], bytes]:
        """What reads one client's commands in multi client mode."""

        def reader(number: int) -> bytes:
            if client_fd not in self.clients:
                return b''
            try:
                data = self.clients[client_fd].socket.recv(number)
                if not data:
                    # EOF - client closed
                    self._disconnect_client(client_fd)
                return data
            except OSError as exc:
                if exc.errno in error.block:
                    return b''
                self._disconnect_client(client_fd)
                return b''

        return reader

    def _client_writer(self, client_fd: int) -> Callable[[bytes], int]:
        """What forwards one client's commands to the daemon, and marks it as the one to answer."""

        def writer(line: bytes) -> int:
            # Fix 2: Use thread-safe setter for active client
            self.response_router.set_active_client(client_fd)
            try:
                return os.write(self._stdout, line)
            except OSError as exc:
                if exc.errno in error.block:
                    return 0
                sys.exit(1)

        return writer

    def _reading_list(self) -> list[int | None] | None:
        """The descriptors to poll in this state, or None once the server socket is closed."""
        if self.multi_client_mode:
            # Multi-client mode: monitor all client FDs
            reading: list[int | None] = [self._stdin, *self.clients.keys()]
            if self.server_socket:
                reading.append(self.server_socket.fileno())
            return reading
        if self.client_fd:
            # Legacy single-client mode. The server socket stays polled so that a second
            # client is told why it cannot connect, rather than left in the accept queue.
            reading = [self._stdin, self.client_fd]
            if self.server_socket:
                reading.append(self.server_socket.fileno())
            return reading
        if self.server_socket:
            return [self._stdin, self.server_socket.fileno()]
        return None

    def _accept(self, server_socket: socket.socket) -> bool:
        """Take the connection waiting on the server socket, False if that failed."""
        try:
            new_socket, _ = server_socket.accept()
            if self.multi_client_mode:
                self._accept_multi(new_socket)
            else:
                self._accept_single(new_socket)
        except OSError:
            return False
        return True

    def _accept_multi(self, new_socket: socket.socket) -> None:
        if len(self.clients) >= self.max_clients:
            # Max clients reached - reject
            self._turn_away(new_socket, b'error: maximum concurrent clients reached\ndone\n')
            return

        new_socket.setblocking(False)
        new_fd = new_socket.fileno()
        self.clients[new_fd] = ClientConnection(socket=new_socket, fd=new_fd)

        # Initialize data structures for client
        self._read[new_fd] = self._client_reader(new_fd)
        self._write[new_fd] = self._client_writer(new_fd)
        self._backlog[new_fd] = Backlog()
        self._store[new_fd] = b''

    def _accept_single(self, new_socket: socket.socket) -> None:
        if self.client_socket:
            # Already have a client - reject immediately
            self._turn_away(new_socket, b'error: another CLI client is already connected\ndone\n')
            return

        self.client_socket = new_socket
        self.client_socket.setblocking(False)
        self.client_fd = self.client_socket.fileno()

        # Initialize data structures for client
        self._read[self.client_fd] = self._socket_reader
        self._write[self.client_fd] = self._std_writer  # Forward socket commands to ExaBGP stdout
        self._backlog[self.client_fd] = Backlog()
        self._store[self.client_fd] = b''

        # Update write destinations
        self._write[self._stdin] = self._socket_writer  # Forward ExaBGP responses to socket

    def _read_multi(self, ready: list[int]) -> None:
        for client_fd in list(self.clients.keys()):
            if client_fd in ready:
                self._consume(client_fd)
                # Check if client disconnected
                if client_fd not in self.clients:
                    # Cleanup happened in socket reader
                    self._forget(client_fd)

    def _read_single(self, ready: list[int]) -> bool:
        """Read the client's commands, True if it has left."""
        if not (self.client_fd and self.client_fd in ready):
            return False
        self._consume(self.client_fd)
        # Check if client disconnected (empty read)
        if not (self.client_fd and not self.client_socket):
            return False

        # Cleanup happened in socket_reader/socket_writer. The daemon is not told: it keeps
        # no list of clients, and the 'done' answering a 'bye' could reach the next client
        # as the answer to its first command.
        self._forget(self.client_fd)
        self._write[self._stdin] = None
        self.client_fd = None  # Clear fd after cleanup
        return True

    def _forward_lines(self, source: int, writer: Callable[[bytes], int]) -> None:
        """Hand each complete line held for source to writer, until one is not taken."""
        while b'\n' in self._store[source]:
            line, rest = self._store[source].split(b'\n', 1)
            sent = writer(line + b'\n')
            if sent:
                self._store[source] = rest
                continue
            break

        if self._backlog.get(source):
            self._grow(source, self._backlog[source].popleft())

    def _route_daemon_output(self) -> None:
        """Multi client: queue each line from the daemon for the client(s) it is for."""
        while b'\n' in self._store[self._stdin]:
            line, rest = self._store[self._stdin].split(b'\n', 1)
            self.response_router.route_response(line + b'\n', self.clients)
            self._store[self._stdin] = rest

        if self._backlog[self._stdin]:
            self._grow(self._stdin, self._backlog[self._stdin].popleft())

    def _flush_client_queues(self) -> None:
        for client_fd in list(self.clients.keys()):
            if client_fd not in self.clients:
                continue
            client = self.clients[client_fd]
            while client.write_queue:
                line = client.write_queue[0]
                try:
                    sent = client.socket.send(line)
                except OSError as exc:
                    if exc.errno not in error.block:
                        # Client disconnected
                        self._disconnect_client(client_fd)
                        self._forget(client_fd)
                    break  # a blocked socket is tried again next time round
                if sent != len(line):
                    # Partial send - update buffer
                    client.write_queue[0] = line[sent:]
                    break
                client.write_queue.popleft()

    def _forward_client_commands(self) -> None:
        """Multi client: pass each client's complete commands to the daemon."""
        for client_fd in list(self.clients.keys()):
            if client_fd not in self.clients or client_fd not in self._store:
                continue
            writer = self._write.get(client_fd)
            if writer:
                self._forward_lines(client_fd, writer)

    def _write_single(self) -> None:
        """Single client: forward both ways, or drop what the daemon says with no one to hear it."""
        for source in list(self._store.keys()):
            if source not in self._store:
                continue
            writer = self._write.get(source)
            if not writer:
                # No client connected, discard data
                self._store[source] = b''
                self._backlog[source].clear()
                continue
            self._forward_lines(source, writer)

    def loop(self) -> None:
        """Main event loop."""
        standard_in = self._stdin = sys.stdin.fileno()
        self._stdout = sys.stdout.fileno()

        self._enable_ack()

        # Data structures for buffering
        self._read = {standard_in: self._std_reader}
        self._write = {standard_in: None}  # Will be set to socket_writer when client connects
        self._backlog = {standard_in: Backlog()}
        self._store = {standard_in: b''}

        while True:
            reading = self._reading_list()
            if reading is None:
                # Server socket closed during cleanup - exit gracefully
                break

            ready = self.read_on(reading)

            if not ready and not self.client_socket and not self.clients:
                # Timeout, no client - continue waiting
                continue

            # Accept new client connection
            if self.server_socket and self.server_socket.fileno() in ready and not self._accept(self.server_socket):
                continue

            # Read from client sockets
            if self.multi_client_mode:
                self._read_multi(ready)
            elif self._read_single(ready):
                # the client left, and nothing is left to forward this time round
                continue

            # Read from stdin (ExaBGP responses)
            if standard_in in ready:
                self._consume(standard_in)

            # Write pending data
            if self.multi_client_mode:
                self._route_daemon_output()
                self._flush_client_queues()
                self._forward_client_commands()
            else:
                self._write_single()

    def run(self) -> None:
        """Run the socket server."""
        if not self.init():
            sys.exit(1)
        try:
            self.loop()
        except KeyboardInterrupt:
            self.cleanup()
            sys.exit(0)
        except Exception as exc:
            sys.stderr.write(str(exc))
            sys.stderr.write('\n\n')
            sys.stderr.flush()
            traceback.print_exc(file=sys.stderr)
            sys.stderr.flush()
            self.cleanup()
            sys.exit(1)


def main(location: str = '') -> None:
    """Entry point for socket-based CLI control process."""
    if not location:
        location = os.environ.get('exabgp_cli_socket', '')
    if not location:
        argv_str = ' '.join(sys.argv)
        sys.stderr.write(f'usage {sys.executable} {argv_str}\n')
        sys.stderr.write(
            "run with 'env exabgp_cli_socket=<location>' if you are trying to mess with ExaBGP's internals\n"
        )
        sys.stderr.flush()
        sys.exit(1)
    Control(location).run()


if __name__ == '__main__':
    main()
