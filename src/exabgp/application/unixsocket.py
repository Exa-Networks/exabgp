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
from collections import deque

from exabgp.reactor.network.error import error

kb = 1024
mb = kb * 1024


def unix_socket(root, socketname='exabgp'):
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
            except Exception:
                pass

    for location in locations:
        socket_path = location + socketname + '.sock'
        try:
            if stat.S_ISSOCK(os.stat(socket_path).st_mode):
                os.environ['exabgp_cli_socket'] = location
                return [location]
        except Exception:
            continue

    return locations


def env(app, section, name, default):
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

    def __init__(self, location):
        # Check for explicit socket path override
        explicit_path = os.environ.get('exabgp_api_socketpath', '')
        if explicit_path:
            self.socket_path = explicit_path
        else:
            socketname = env('exabgp', 'api', 'socketname', 'exabgp')
            self.socket_path = location + socketname + '.sock'

        self.server_socket = None
        self.client_socket = None
        self.client_fd = None

    def init(self):
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
            self.server_socket.listen(1)  # Single connection at a time
            self.server_socket.setblocking(False)
        except OSError as exc:
            sys.stdout.write(f'error: could not create socket {os.path.abspath(self.socket_path)}: {exc}\n')
            sys.stdout.flush()
            return False

        signal.signal(signal.SIGINT, self.terminate)
        signal.signal(signal.SIGTERM, self.terminate)
        return True

    def cleanup_client(self):
        """Clean up client connection only (keep server listening).

        Note: Only closes the socket, not clearing client_fd.
        The main loop will detect this state and clean up data structures.
        """
        if self.client_socket:
            try:
                self.client_socket.close()
            except Exception:
                pass
            self.client_socket = None
            # Do NOT clear client_fd here - main loop needs it to clean up dicts

    def cleanup(self):
        """Clean up all resources (server shutdown)."""
        self.cleanup_client()
        self.client_fd = None  # Full cleanup includes clearing fd

        if self.server_socket:
            try:
                self.server_socket.close()
            except Exception:
                pass
            self.server_socket = None

        # Remove socket file
        try:
            if os.path.exists(self.socket_path):
                os.unlink(self.socket_path)
        except Exception:
            pass

    def terminate(self, ignore=None, me=None):
        """Signal handler for clean shutdown."""
        if self.terminating:
            sys.exit(1)
        self.terminating = True
        self.cleanup()
        sys.exit(0)

    def read_on(self, reading):
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

    def loop(self):
        """Main event loop."""
        standard_in = sys.stdin.fileno()
        standard_out = sys.stdout.fileno()

        # Enable ACK for this CLI control process
        try:
            os.write(standard_out, b'enable-ack\n')
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

        def monitor(function):
            def wrapper(*args):
                r = function(*args)
                return r

            return wrapper

        @monitor
        def std_reader(number):
            try:
                return os.read(standard_in, number)
            except OSError as exc:
                if exc.errno in error.block:
                    return b''
                sys.exit(1)

        @monitor
        def std_writer(line):
            try:
                return os.write(standard_out, line)
            except OSError as exc:
                if exc.errno in error.block:
                    return 0
                sys.exit(1)

        @monitor
        def socket_reader(number):
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

        @monitor
        def socket_writer(line):
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
        reading = [standard_in, self.server_socket.fileno()]

        # Data structures for buffering
        read = {standard_in: std_reader}
        write = {standard_in: None}  # Will be set to socket_writer when client connects
        backlog = {standard_in: deque()}
        store = {standard_in: b''}

        def consume(source):
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
            if self.client_fd:
                reading = [standard_in, self.client_fd]
            elif self.server_socket:
                reading = [standard_in, self.server_socket.fileno()]
            else:
                # Server socket closed during cleanup - exit gracefully
                break

            ready = self.read_on(reading)

            if not ready and not self.client_socket:
                # Timeout, no client - continue waiting
                continue

            # Accept new client connection
            if self.server_socket and self.server_socket.fileno() in ready and not self.client_socket:
                try:
                    self.client_socket, _ = self.server_socket.accept()
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

            # Read from client socket
            if self.client_fd and self.client_fd in ready:
                consume(self.client_fd)
                # Check if client disconnected (empty read)
                if self.client_fd and not self.client_socket:
                    # Cleanup happened in socket_reader/socket_writer
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

    def run(self):
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


def main(location=''):
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
