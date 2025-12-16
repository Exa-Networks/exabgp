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
import signal
import select
import socket
import traceback
import re
import time
import threading
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable

from exabgp.reactor.network.error import error

kb = 1024
mb = kb * 1024


class ResponseType(Enum):
    """Type of response from ExaBGP reactor."""

    UNICAST = 'unicast'  # Response to specific client command
    BROADCAST = 'broadcast'  # Event broadcast to all clients


@dataclass
class ClientConnection:
    """Track individual CLI client connection."""

    socket: socket.socket
    fd: int
    uuid: str | None = None  # From initial ping command
    last_ping: float = 0.0
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

        # Check JSON format
        if line.startswith('{'):
            try:
                import json

                parsed = json.loads(line)
                if isinstance(parsed, dict) and 'request_id' in parsed:
                    return str(parsed['request_id'])
            except (json.JSONDecodeError, ValueError):
                pass

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
            except OSError:
                pass

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

    def _disconnect_client(self, fd: int, standard_out: int | None = None) -> None:
        """Disconnect a specific client (multi-client mode)."""
        if fd not in self.clients:
            return

        client = self.clients[fd]

        # Notify reactor that client disconnected
        if standard_out is not None and client.uuid:
            try:
                os.write(standard_out, f'bye {client.uuid}\n'.encode())
            except OSError:
                pass

        # Close socket
        try:
            client.socket.close()
        except OSError:
            pass

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
            try:
                self.client_socket.close()
            except OSError:
                pass
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
            try:
                self.server_socket.close()
            except OSError:
                pass
            self.server_socket = None

        # Remove socket file
        try:
            if os.path.exists(self.socket_path):
                os.unlink(self.socket_path)
        except OSError:
            pass

    def terminate(self, signum: int | None = None, frame: object = None) -> None:
        """Signal handler for clean shutdown."""
        if self.terminating:
            sys.exit(1)
        self.terminating = True
        self.cleanup()
        sys.exit(0)

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

    def loop(self) -> None:
        """Main event loop."""
        standard_in = sys.stdin.fileno()
        standard_out = sys.stdout.fileno()

        # Enable ACK for this CLI control process (v6 API format)
        try:
            os.write(standard_out, b'session ack enable\n')
            # Read and discard the 'done' response
            poller = select.poll()
            poller.register(standard_in, select.POLLIN)
            if poller.poll(1000):
                response = b''
                while b'\n' not in response:
                    chunk = os.read(standard_in, 1024)
                    if not chunk:
                        break
                    response += chunk
        except OSError:
            pass

        def std_reader(number: int) -> bytes:
            try:
                return os.read(standard_in, number)
            except OSError as exc:
                if exc.errno in error.block:
                    return b''
                sys.exit(1)

        def std_writer(line: bytes) -> int:
            try:
                return os.write(standard_out, line)
            except OSError as exc:
                if exc.errno in error.block:
                    return 0
                sys.exit(1)

        def socket_reader(number: int) -> bytes:
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

        def socket_writer(line: bytes) -> int:
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

        # File descriptors to monitor
        server_fd = self.server_socket.fileno() if self.server_socket else None
        reading: list[int | None] = [standard_in, server_fd]

        # Data structures for buffering
        read: dict[int, Callable[[int], bytes]] = {standard_in: std_reader}
        write: dict[int, Callable[[bytes], int] | None] = {
            standard_in: None
        }  # Will be set to socket_writer when client connects
        backlog: dict[int, deque[bytes]] = {standard_in: deque()}
        store: dict[int, bytes] = {standard_in: b''}

        def consume(source: int) -> None:
            if not backlog[source] and b'\n' not in store[source]:
                store[source] += read[source](1024)
            else:
                backlog[source].append(read[source](1024))
                # Memory limit check
                if len(backlog) > 100 * mb:
                    sys.stderr.write('using too much memory - exiting\n')
                    sys.stderr.flush()
                    sys.exit(1)

        while True:
            # Update reading list based on connection state
            if self.multi_client_mode:
                # Multi-client mode: monitor all client FDs
                reading = [standard_in] + list(self.clients.keys())
                if self.server_socket:
                    reading.append(self.server_socket.fileno())
            elif self.client_fd:
                # Legacy single-client mode
                reading = [standard_in, self.client_fd]
            elif self.server_socket:
                reading = [standard_in, self.server_socket.fileno()]
            else:
                # Server socket closed during cleanup - exit gracefully
                break

            ready = self.read_on(reading)

            if not ready and not self.client_socket and not self.clients:
                # Timeout, no client - continue waiting
                continue

            # Accept new client connection
            if self.server_socket and self.server_socket.fileno() in ready:
                try:
                    new_socket, _ = self.server_socket.accept()

                    if self.multi_client_mode:
                        # Multi-client mode
                        if len(self.clients) >= self.max_clients:
                            # Max clients reached - reject
                            try:
                                new_socket.setblocking(True)
                                new_socket.sendall(b'error: maximum concurrent clients reached\ndone\n')
                                try:
                                    new_socket.shutdown(socket.SHUT_WR)
                                except OSError:
                                    pass
                                new_socket.close()
                            except OSError:
                                try:
                                    new_socket.close()
                                except OSError:
                                    pass
                        else:
                            # Accept new client
                            new_socket.setblocking(False)
                            new_fd = new_socket.fileno()

                            # Create client connection
                            client = ClientConnection(socket=new_socket, fd=new_fd)
                            self.clients[new_fd] = client

                            # Create per-client socket reader/writer with client-specific fd
                            def make_socket_reader(client_fd: int) -> Callable[[int], bytes]:
                                def reader(number: int) -> bytes:
                                    if client_fd not in self.clients:
                                        return b''
                                    try:
                                        data = self.clients[client_fd].socket.recv(number)
                                        if not data:
                                            # EOF - client closed
                                            self._disconnect_client(client_fd, standard_out)
                                        return data
                                    except OSError as exc:
                                        if exc.errno in error.block:
                                            return b''
                                        self._disconnect_client(client_fd, standard_out)
                                        return b''

                                return reader

                            def make_std_writer_for_client(client_fd: int) -> Callable[[bytes], int]:
                                def writer(line: bytes) -> int:
                                    # Fix 2: Use thread-safe setter for active client
                                    self.response_router.set_active_client(client_fd)
                                    try:
                                        return os.write(standard_out, line)
                                    except OSError as exc:
                                        if exc.errno in error.block:
                                            return 0
                                        sys.exit(1)

                                return writer

                            # Initialize data structures for client
                            read[new_fd] = make_socket_reader(new_fd)
                            write[new_fd] = make_std_writer_for_client(new_fd)
                            backlog[new_fd] = deque()
                            store[new_fd] = b''
                    else:
                        # Single-client mode (legacy)
                        if self.client_socket:
                            # Already have a client - reject immediately
                            try:
                                new_socket.setblocking(True)
                                new_socket.sendall(b'error: another CLI client is already connected\ndone\n')
                                try:
                                    new_socket.shutdown(socket.SHUT_WR)
                                except OSError:
                                    pass  # Ignore shutdown errors
                                new_socket.close()
                            except OSError:
                                try:
                                    new_socket.close()
                                except OSError:
                                    pass
                        else:
                            # No client - accept this connection
                            self.client_socket = new_socket
                            self.client_socket.setblocking(False)
                            self.client_fd = self.client_socket.fileno()

                            # Initialize data structures for client
                            read[self.client_fd] = socket_reader
                            write[self.client_fd] = std_writer  # Forward socket commands to ExaBGP stdout
                            backlog[self.client_fd] = deque()
                            store[self.client_fd] = b''

                            # Update write destinations
                            write[standard_in] = socket_writer  # Forward ExaBGP responses to socket
                except OSError:
                    continue

            # Read from client sockets
            if self.multi_client_mode:
                # Multi-client mode: check all clients
                for client_fd in list(self.clients.keys()):
                    if client_fd in ready:
                        consume(client_fd)
                        # Check if client disconnected
                        if client_fd not in self.clients:
                            # Cleanup happened in socket reader
                            # Remove from data structures
                            if client_fd in read:
                                del read[client_fd]
                            if client_fd in write:
                                del write[client_fd]
                            if client_fd in backlog:
                                del backlog[client_fd]
                            if client_fd in store:
                                del store[client_fd]
            else:
                # Legacy single-client mode
                if self.client_fd and self.client_fd in ready:
                    consume(self.client_fd)
                    # Check if client disconnected (empty read)
                    if self.client_fd and not self.client_socket:
                        # Cleanup happened in socket_reader/socket_writer
                        # Notify reactor that client disconnected (clears active_client_uuid)
                        try:
                            os.write(standard_out, b'bye\n')
                        except OSError:
                            pass

                        # Remove client from data structures
                        if self.client_fd in read:
                            del read[self.client_fd]
                        if self.client_fd in write:
                            del write[self.client_fd]
                        if self.client_fd in backlog:
                            del backlog[self.client_fd]
                        if self.client_fd in store:
                            del store[self.client_fd]
                        write[standard_in] = None
                        self.client_fd = None  # Clear fd after cleanup
                        continue

            # Read from stdin (ExaBGP responses)
            if standard_in in ready:
                consume(standard_in)

            # Write pending data
            if self.multi_client_mode:
                # Multi-client mode: route responses to appropriate clients
                # Process stdin responses (from ExaBGP)
                while b'\n' in store[standard_in]:
                    line, rest = store[standard_in].split(b'\n', 1)
                    # Route this response to appropriate client(s)
                    self.response_router.route_response(line + b'\n', self.clients)
                    store[standard_in] = rest

                if backlog[standard_in]:
                    store[standard_in] += backlog[standard_in].popleft()

                # Flush client write queues
                for client_fd in list(self.clients.keys()):
                    if client_fd not in self.clients:
                        continue
                    client = self.clients[client_fd]
                    while client.write_queue:
                        line = client.write_queue[0]
                        try:
                            sent = client.socket.send(line)
                            if sent == len(line):
                                client.write_queue.popleft()
                            else:
                                # Partial send - update buffer
                                client.write_queue[0] = line[sent:]
                                break
                        except OSError as exc:
                            if exc.errno in error.block:
                                break  # Would block, try later
                            else:
                                # Client disconnected
                                self._disconnect_client(client_fd, standard_out)
                                # Remove from data structures
                                if client_fd in read:
                                    del read[client_fd]
                                if client_fd in write:
                                    del write[client_fd]
                                if client_fd in backlog:
                                    del backlog[client_fd]
                                if client_fd in store:
                                    del store[client_fd]
                                break

                # Process client commands (write to stdout)
                for client_fd in list(self.clients.keys()):
                    if client_fd not in self.clients or client_fd not in store:
                        continue
                    writer = write.get(client_fd)
                    if not writer:
                        continue

                    while b'\n' in store[client_fd]:
                        line, rest = store[client_fd].split(b'\n', 1)
                        sent = writer(line + b'\n')
                        if sent:
                            store[client_fd] = rest
                            continue
                        break

                    if backlog.get(client_fd):
                        store[client_fd] += backlog[client_fd].popleft()
            else:
                # Legacy single-client mode
                sources = list(store.keys())
                for source in sources:
                    if source not in store:
                        continue
                    writer = write.get(source)
                    if not writer:
                        # No client connected, discard data
                        store[source] = b''
                        backlog[source].clear()
                        continue

                    while b'\n' in store[source]:
                        line, rest = store[source].split(b'\n', 1)
                        sent = writer(line + b'\n')
                        if sent:
                            store[source] = rest
                            continue
                        break

                    if backlog[source]:
                        store[source] += backlog[source].popleft()

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
