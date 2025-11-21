#!/usr/bin/env python3

"""Interactive REPL mode for ExaBGP CLI with readline support"""

from __future__ import annotations

import json
import os
import re
import sys
import readline
import atexit
import ctypes
import socket as sock
import threading
import time
import signal
from dataclasses import dataclass
from queue import Queue, Empty
from typing import List, Optional, Callable, Dict, Tuple, Union

from exabgp.application.shortcuts import CommandShortcuts
from exabgp.application.pipe import named_pipe
from exabgp.application.unixsocket import unix_socket
from exabgp.environment import ROOT
from exabgp.reactor.api.command.registry import CommandRegistry


# ANSI color codes
class Colors:
    """ANSI color codes for terminal output"""

    RESET = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'

    # Foreground colors
    BLACK = '\033[30m'
    RED = '\033[31m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    BLUE = '\033[34m'
    MAGENTA = '\033[35m'
    CYAN = '\033[36m'
    WHITE = '\033[37m'

    # Bright colors
    BRIGHT_BLACK = '\033[90m'
    BRIGHT_RED = '\033[91m'
    BRIGHT_GREEN = '\033[92m'
    BRIGHT_YELLOW = '\033[93m'
    BRIGHT_BLUE = '\033[94m'
    BRIGHT_MAGENTA = '\033[95m'
    BRIGHT_CYAN = '\033[96m'
    BRIGHT_WHITE = '\033[97m'

    @classmethod
    def supports_color(cls) -> bool:
        """Check if terminal supports ANSI colors"""
        # Check if stdout is a terminal
        if not hasattr(sys.stdout, 'isatty') or not sys.stdout.isatty():
            return False

        # Check TERM environment variable
        term = os.environ.get('TERM', '')
        if term in ('dumb', ''):
            return False

        # Check NO_COLOR environment variable (https://no-color.org/)
        if os.environ.get('NO_COLOR'):
            return False

        return True


class PersistentSocketConnection:
    """Persistent Unix socket connection with background health monitoring"""

    def __init__(self, socket_path: str):
        self.socket_path = socket_path
        self.socket = None
        self.daemon_uuid = None
        self.last_ping_time = 0
        self.consecutive_failures = 0
        self.max_failures = 3
        self.health_interval = 10  # seconds
        self.running = True
        self.reconnecting = False
        self.command_in_progress = False  # Track if user command is being executed
        self.pending_user_command = False  # Track if waiting for user command response
        self.lock = threading.Lock()

        # Client identity for connection tracking
        import uuid as uuid_lib

        self.client_uuid = str(uuid_lib.uuid4())
        self.client_start_time = time.time()

        # Response handling
        self.pending_responses = Queue()
        self.response_buffer = ''

        # Connect
        self._connect()

        # Send initial synchronous ping to get daemon UUID (before showing prompt)
        self._initial_ping()

        # Setup signal handler for graceful shutdown
        self._setup_signal_handler()

        # Start background threads
        self.reader_thread = threading.Thread(target=self._read_loop, daemon=True)
        self.reader_thread.start()

        self.health_thread = threading.Thread(target=self._health_monitor, daemon=True)
        self.health_thread.start()

    def _connect(self):
        """Establish socket connection"""
        self.socket = sock.socket(sock.AF_UNIX, sock.SOCK_STREAM)
        full_path = self.socket_path if self.socket_path.endswith('.sock') else self.socket_path + 'exabgp.sock'
        self.socket.connect(full_path)
        self.socket.settimeout(0.5)  # Initial timeout for sync ping

    def _initial_ping(self):
        """Send initial synchronous ping to get daemon UUID before starting background threads"""
        try:
            # Send ping
            ping_cmd = f'ping {self.client_uuid} {self.client_start_time}\n'
            try:
                self.socket.sendall(ping_cmd.encode('utf-8'))
            except (BrokenPipeError, ConnectionResetError):
                # Connection rejected before we could send
                sys.stderr.write('\n')
                sys.stderr.write('╔════════════════════════════════════════════════════════╗\n')
                sys.stderr.write('║  ERROR: Another CLI client is already connected        ║\n')
                sys.stderr.write('╠════════════════════════════════════════════════════════╣\n')
                sys.stderr.write('║  Only one CLI client can be active at a time.          ║\n')
                sys.stderr.write('║  Please close the other client first.                  ║\n')
                sys.stderr.write('╚════════════════════════════════════════════════════════╝\n')
                sys.stderr.write('\n')
                sys.stderr.flush()
                sys.exit(1)

            # Read response synchronously
            response_buffer = ''
            while True:
                data = self.socket.recv(4096)
                if not data:
                    # Connection closed - likely another client already connected
                    sys.stderr.write('\n')
                    sys.stderr.write('╔════════════════════════════════════════════════════════╗\n')
                    sys.stderr.write('║  ERROR: Another CLI client is already connected        ║\n')
                    sys.stderr.write('╠════════════════════════════════════════════════════════╣\n')
                    sys.stderr.write('║  Only one CLI client can be active at a time.          ║\n')
                    sys.stderr.write('║  Please close the other client first.                  ║\n')
                    sys.stderr.write('╚════════════════════════════════════════════════════════╝\n')
                    sys.stderr.write('\n')
                    sys.stderr.flush()
                    sys.exit(1)

                response_buffer += data.decode('utf-8')

                # Check if we have complete response (pong + done OR error + done)
                if '\ndone\n' in response_buffer or response_buffer.endswith('done\n'):
                    break

            # Check for immediate rejection (another client already connected)
            if response_buffer.startswith('error:') and 'already connected' in response_buffer:
                sys.stderr.write('\n')
                sys.stderr.write('╔════════════════════════════════════════════════════════╗\n')
                sys.stderr.write('║  ERROR: Another CLI client is already connected        ║\n')
                sys.stderr.write('╠════════════════════════════════════════════════════════╣\n')
                sys.stderr.write('║  Only one CLI client can be active at a time.          ║\n')
                sys.stderr.write('║  Please close the other client first.                  ║\n')
                sys.stderr.write('╚════════════════════════════════════════════════════════╝\n')
                sys.stderr.write('\n')
                sys.stderr.flush()
                sys.exit(1)

            # Parse response (handle both JSON and text formats)
            lines = response_buffer.split('\n')
            uuid_found = False
            is_active = True

            for line in lines:
                line = line.strip()
                if not line or line == 'done':
                    continue

                # Try JSON format first
                if line.startswith('{'):
                    try:
                        import json

                        parsed = json.loads(line)
                        if isinstance(parsed, dict) and 'pong' in parsed:
                            self.daemon_uuid = parsed['pong']
                            is_active = parsed.get('active', True)
                            uuid_found = True
                            break
                    except (json.JSONDecodeError, ValueError):
                        pass

                # Try text format
                if line.startswith('pong '):
                    parts = line.split()
                    if len(parts) >= 2:
                        self.daemon_uuid = parts[1]
                        uuid_found = True

                        # Check if we're active
                        if len(parts) >= 3 and parts[2].startswith('active='):
                            is_active = parts[2].split('=')[1].lower() == 'true'
                        break

            if uuid_found:
                if not is_active:
                    # Another client is already active
                    sys.stderr.write('\n')
                    sys.stderr.write('╔════════════════════════════════════════════════════════╗\n')
                    sys.stderr.write('║  ERROR: Another CLI client is already connected        ║\n')
                    sys.stderr.write('╠════════════════════════════════════════════════════════╣\n')
                    sys.stderr.write('║  Only one CLI client can be active at a time.          ║\n')
                    sys.stderr.write('║  Please close the other client first, or wait for      ║\n')
                    sys.stderr.write('║  the active client to disconnect.                      ║\n')
                    sys.stderr.write('╚════════════════════════════════════════════════════════╝\n')
                    sys.stderr.write('\n')
                    sys.stderr.flush()
                    sys.exit(1)

                # Print connection message BEFORE returning (so it appears before banner)
                sys.stderr.write(f'✓ Connected to ExaBGP daemon (UUID: {self.daemon_uuid})\n')
                sys.stderr.flush()

            # Switch to non-blocking for background threads
            self.socket.settimeout(0.1)

        except sock.timeout:
            sys.stderr.write('\n')
            sys.stderr.write('╔════════════════════════════════════════════════════════╗\n')
            sys.stderr.write('║  ERROR: Connection timeout                             ║\n')
            sys.stderr.write('╠════════════════════════════════════════════════════════╣\n')
            sys.stderr.write('║  ExaBGP daemon is not responding to commands.          ║\n')
            sys.stderr.write('║                                                        ║\n')
            sys.stderr.write('║  Possible causes:                                      ║\n')
            sys.stderr.write('║    • Another CLI client is already connected           ║\n')
            sys.stderr.write('║    • The daemon crashed after accepting connection     ║\n')
            sys.stderr.write('║                                                        ║\n')
            sys.stderr.write('║  Try closing any other CLI clients first.              ║\n')
            sys.stderr.write('╚════════════════════════════════════════════════════════╝\n')
            sys.stderr.write('\n')
            sys.stderr.flush()
            sys.exit(1)
        except Exception as exc:
            sys.stderr.write('\n')
            sys.stderr.write('╔════════════════════════════════════════════════════════╗\n')
            sys.stderr.write('║  ERROR: Failed to communicate with ExaBGP daemon       ║\n')
            sys.stderr.write('╠════════════════════════════════════════════════════════╣\n')
            sys.stderr.write(f'║  {str(exc):<54} ║\n')
            sys.stderr.write('╚════════════════════════════════════════════════════════╝\n')
            sys.stderr.write('\n')
            sys.stderr.flush()
            sys.exit(1)

    def _setup_signal_handler(self) -> None:
        """Setup signal handler for graceful shutdown from background threads"""

        def signal_handler(signum, frame):
            """Handle SIGUSR1 by setting running flag to False"""
            self.running = False
            # Re-raise KeyboardInterrupt to break out of input()
            raise KeyboardInterrupt()

        # Use SIGUSR1 for graceful shutdown signaling
        signal.signal(signal.SIGUSR1, signal_handler)

    def _signal_shutdown(self) -> None:
        """Send shutdown signal to main thread (called from background thread)"""
        try:
            # Send SIGUSR1 to main thread to interrupt input()
            os.kill(os.getpid(), signal.SIGUSR1)
        except Exception:
            pass

    def _reconnect(self, max_attempts=3, retry_delay=2) -> bool:
        """
        Attempt to reconnect to ExaBGP daemon

        Args:
            max_attempts: Number of reconnection attempts
            retry_delay: Seconds to wait between attempts

        Returns:
            True if reconnection successful, False otherwise
        """
        # Signal to health monitor to stop pinging during reconnection
        self.reconnecting = True

        sys.stderr.write('\n')
        sys.stderr.write('⚠ Connection to ExaBGP daemon lost, attempting to reconnect...\n')
        sys.stderr.flush()

        # Close old socket
        if self.socket:
            try:
                self.socket.close()
            except Exception:
                pass
            self.socket = None

        # Try to reconnect
        for attempt in range(1, max_attempts + 1):
            try:
                sys.stderr.write(f'  Attempt {attempt}/{max_attempts}...')
                sys.stderr.flush()

                # Wait before retry (except first attempt)
                if attempt > 1:
                    time.sleep(retry_delay)

                # Reconnect
                self._connect()

                # Send initial ping to verify connection and get new UUID
                self._initial_ping()

                # Success!
                sys.stderr.write(' ✓ Reconnected successfully!\n')

                # Print reconnection message in green
                reconnect_msg = f'✓ Reconnected to ExaBGP daemon (UUID: {self.daemon_uuid})'
                if Colors.supports_color():
                    sys.stderr.write(f'{Colors.GREEN}{reconnect_msg}{Colors.RESET}\n\n')
                else:
                    sys.stderr.write(f'{reconnect_msg}\n\n')
                sys.stderr.flush()

                # Redraw prompt with preserved input
                # readline.redisplay() from background thread doesn't work - must manually redraw
                try:
                    import readline

                    # Get what user was typing
                    buffer = readline.get_line_buffer()

                    # Manually redraw using ANSI codes
                    # \r - return to start of line
                    # \033[K - clear from cursor to end of line
                    sys.stdout.write('\r\033[K')

                    # Write prompt with color
                    if Colors.supports_color():
                        prompt = f'{Colors.BOLD}{Colors.GREEN}exabgp{Colors.RESET}{Colors.BOLD}>{Colors.RESET} '
                    else:
                        prompt = 'exabgp> '
                    sys.stdout.write(prompt)

                    # Write the preserved input
                    sys.stdout.write(buffer)

                    # CRITICAL: Flush to make it appear immediately
                    sys.stdout.flush()

                except Exception:
                    # Readline not available or failed, just write prompt manually
                    sys.stdout.write('\r\033[K')
                    if Colors.supports_color():
                        prompt = f'{Colors.BOLD}{Colors.GREEN}exabgp{Colors.RESET}{Colors.BOLD}>{Colors.RESET} '
                    else:
                        prompt = 'exabgp> '
                    sys.stdout.write(prompt)
                    sys.stdout.flush()

                # Success - resume health monitoring
                self.reconnecting = False
                return True

            except SystemExit:
                # _initial_ping raised SystemExit with user-friendly error (e.g., another client active)
                # Stop all activity before exiting
                self.reconnecting = False
                self.running = False
                raise
            except Exception as exc:
                sys.stderr.write(f' ✗ Failed: {exc}\n')
                sys.stderr.flush()

        # All attempts failed - stop all activity
        self.reconnecting = False
        self.running = False

        sys.stderr.write('\n')
        sys.stderr.write('╔════════════════════════════════════════════════════════╗\n')
        sys.stderr.write('║  ERROR: Could not reconnect to ExaBGP daemon           ║\n')
        sys.stderr.write('╠════════════════════════════════════════════════════════╣\n')
        sys.stderr.write(f'║  Failed after {max_attempts} attempts.                              ║\n')
        sys.stderr.write('║  Please check if ExaBGP is running.                    ║\n')
        sys.stderr.write('║                                                        ║\n')
        sys.stderr.write('║  Exiting CLI...                                        ║\n')
        sys.stderr.write('╚════════════════════════════════════════════════════════╝\n')
        sys.stderr.write('\n')
        sys.stderr.flush()
        return False

    def _read_loop(self):
        """Background thread: continuously read from socket"""
        while self.running:
            try:
                data = self.socket.recv(4096)
                if not data:
                    # Socket closed - attempt reconnection
                    if not self._reconnect():
                        # Reconnection failed - signal main thread to exit
                        self._signal_shutdown()
                        break
                    # Reconnected successfully, reset buffer and continue
                    self.response_buffer = ''
                    continue

                self.response_buffer += data.decode('utf-8')

                # Parse complete responses (ending with 'done\n' or 'error\n')
                # 'done' marks successful completion, 'error' marks error completion
                completion_found = (
                    '\ndone\n' in self.response_buffer
                    or self.response_buffer.endswith('done\n')
                    or '\nerror\n' in self.response_buffer
                    or self.response_buffer.endswith('error\n')
                )

                while completion_found:
                    # Try 'done' first, then 'error'
                    if '\ndone\n' in self.response_buffer:
                        response, self.response_buffer = self.response_buffer.split('\ndone\n', 1)
                    elif self.response_buffer.endswith('done\n'):
                        response = self.response_buffer[:-5]  # Remove 'done\n'
                        self.response_buffer = ''
                    elif '\nerror\n' in self.response_buffer:
                        response, self.response_buffer = self.response_buffer.split('\nerror\n', 1)
                    elif self.response_buffer.endswith('error\n'):
                        response = self.response_buffer[:-6]  # Remove 'error\n'
                        self.response_buffer = ''
                    else:
                        break  # Should not reach here

                    response = response.strip()

                    # Check for next completion marker
                    completion_found = (
                        '\ndone\n' in self.response_buffer
                        or self.response_buffer.endswith('done\n')
                        or '\nerror\n' in self.response_buffer
                        or self.response_buffer.endswith('error\n')
                    )

                    # Determine if this is a ping response (health check)
                    # Ping responses can be in two formats:
                    # - Text: "pong <uuid> active=true"
                    # - JSON: {"pong": "<uuid>", "active": true}
                    is_ping_response = False
                    if response.startswith('pong '):
                        # Text format ping response
                        is_ping_response = True
                    elif response.startswith('{') and '"pong"' in response and '"active"' in response:
                        # JSON format ping response (check for both pong and active keys)
                        try:
                            import json

                            parsed = json.loads(response)
                            if isinstance(parsed, dict) and 'pong' in parsed and 'active' in parsed:
                                is_ping_response = True
                        except (json.JSONDecodeError, ValueError):
                            pass

                    # Route response based on whether we're waiting for user command
                    with self.lock:
                        waiting_for_user = self.pending_user_command

                    if is_ping_response and not waiting_for_user:
                        # Health check ping response - handle internally
                        self._handle_ping_response(response)
                    else:
                        # User command response (or ping response during user command - route to user)
                        self.pending_responses.put(response)

            except sock.timeout:
                # No data available, continue
                continue
            except Exception as exc:
                if self.running:
                    sys.stderr.write(f'\n\nERROR: Connection to ExaBGP lost: {exc}\n')
                    sys.stderr.write('Press Enter to exit...\n')
                    sys.stderr.flush()
                    # Gracefully shut down the CLI (allows readline cleanup)
                    # Note: Main thread is blocked in input(), so we set flag
                    # and user must press Enter to trigger loop check
                    self.running = False
                break

    def _health_monitor(self):
        """Background thread: send periodic pings"""
        # Initial sync ping already done in __init__, start periodic monitoring
        while self.running:
            # Skip health checks if reconnecting
            if not self.reconnecting:
                current_time = time.time()
                if current_time - self.last_ping_time >= self.health_interval:
                    self._send_ping()

            time.sleep(1)  # Check every second

    def _send_ping(self):
        """Send ping command (internal, not user-initiated)"""
        # Skip if reconnecting or no socket
        if self.reconnecting or not self.socket:
            return

        with self.lock:
            # Skip ping if a user command is in progress or pending
            if self.command_in_progress or self.pending_user_command:
                return

            try:
                # Include client UUID and start time to track active connection
                ping_cmd = f'ping {self.client_uuid} {self.client_start_time}\n'
                self.socket.sendall(ping_cmd.encode('utf-8'))
                self.last_ping_time = time.time()
            except Exception:
                # Socket error - read loop will handle reconnection
                # Don't print error or exit here
                pass

    def _handle_ping_response(self, response: str):
        """Handle pong response from health check

        Supports both text and JSON formats:
        - Text: "pong <uuid> active=true"
        - JSON: {"pong": "<uuid>", "active": true}
        """
        new_uuid = None
        is_active = True  # Default for backward compatibility

        # Try JSON format first
        if response.startswith('{'):
            try:
                import json

                parsed = json.loads(response)
                if isinstance(parsed, dict) and 'pong' in parsed:
                    new_uuid = parsed['pong']
                    is_active = parsed.get('active', True)
            except (json.JSONDecodeError, ValueError):
                pass

        # Fallback to text format
        if new_uuid is None:
            parts = response.split()
            if len(parts) >= 2:
                new_uuid = parts[1]

                # Check if we're the active client (format: "pong <daemon_uuid> active=true/false")
                if len(parts) >= 3 and parts[2].startswith('active='):
                    is_active = parts[2].split('=')[1].lower() == 'true'

        if new_uuid:
            if not is_active:
                # Another CLI client connected and replaced us
                warning = (
                    '\n'
                    '╔════════════════════════════════════════════════════════╗\n'
                    '║  Another CLI client connected                          ║\n'
                    '╠════════════════════════════════════════════════════════╣\n'
                    '║  This session has been replaced by a newer connection  ║\n'
                    '║  Exiting gracefully...                                 ║\n'
                    '╚════════════════════════════════════════════════════════╝\n'
                )
                sys.stderr.write(warning)
                sys.stderr.flush()
                # Another client connected - signal main thread to exit
                self._signal_shutdown()
                return

            if self.daemon_uuid is None:
                # First UUID discovery (shouldn't happen since _initial_ping sets it)
                # But keep as fallback for robustness
                self.daemon_uuid = new_uuid
                # Don't print connection message here - already printed in _initial_ping()
                self.consecutive_failures = 0
            elif new_uuid != self.daemon_uuid:
                # Daemon restarted!
                old_uuid = self.daemon_uuid
                self.daemon_uuid = new_uuid

                warning = (
                    '\n'
                    '╔════════════════════════════════════════════════════════╗\n'
                    '║  WARNING: ExaBGP daemon restarted                      ║\n'
                    '╠════════════════════════════════════════════════════════╣\n'
                    f'║  Previous UUID: {old_uuid:<38} ║\n'
                    f'║  New UUID:      {new_uuid:<38} ║\n'
                    '╚════════════════════════════════════════════════════════╝\n'
                )
                sys.stderr.write(warning)
                sys.stderr.flush()
                self.consecutive_failures = 0
            else:
                # Normal ping response
                self.consecutive_failures = 0
        else:
            # Malformed response
            self.consecutive_failures += 1
            if self.consecutive_failures >= self.max_failures:
                sys.stderr.write(f'ERROR: ExaBGP daemon not responding after {self.max_failures} attempts\n')
                sys.stderr.flush()
                # Daemon not responding - signal main thread to exit
                self._signal_shutdown()
                return

    def send_command(self, command: str) -> str:
        """Send user command and wait for response"""
        # Mark command in progress to prevent ping interference
        with self.lock:
            self.command_in_progress = True
            self.pending_user_command = True

        try:
            # Flush any stale responses from queue (e.g., pending ping responses)
            # This ensures we only get the response to THIS command
            while not self.pending_responses.empty():
                try:
                    self.pending_responses.get_nowait()
                except Empty:
                    break

            # Send command
            try:
                with self.lock:
                    self.socket.sendall((command + '\n').encode('utf-8'))
            except Exception as exc:
                return f'Error: {exc}'

            # Wait for response (with timeout)
            try:
                response = self.pending_responses.get(timeout=5.0)
                return response
            except Empty:
                return 'Error: Timeout waiting for response'
        finally:
            # Always clear the flags when done (even on error/timeout)
            with self.lock:
                self.command_in_progress = False
                self.pending_user_command = False

    def close(self):
        """Close connection and stop threads"""
        try:
            self.running = False

            # Close socket (triggers read thread to exit)
            if self.socket:
                try:
                    # Shutdown socket first (stops I/O operations)
                    self.socket.shutdown(sock.SHUT_RDWR)
                except Exception:
                    pass

                try:
                    # Then close the socket
                    self.socket.close()
                except Exception:
                    pass

            # Give threads a moment to exit
            try:
                time.sleep(0.2)
            except KeyboardInterrupt:
                # User is impatient, exit immediately
                pass
        except KeyboardInterrupt:
            # Ctrl+C during cleanup - exit immediately without error
            pass


@dataclass
class CompletionItem:
    """Metadata for a single completion item"""

    value: str  # The actual completion text
    description: Optional[str] = None  # Human-readable description
    item_type: str = 'option'  # Type: 'option', 'neighbor', 'command', 'keyword'


class CommandCompleter:
    """Tab completion for ExaBGP commands using readline with dynamic command discovery"""

    def __init__(self, send_command: Callable[[str], str], get_neighbors: Optional[Callable[[], List[str]]] = None):
        """
        Initialize completer

        Args:
            send_command: Function to send commands to ExaBGP
            get_neighbors: Optional function to fetch neighbor IPs for completion
        """
        self.send_command = send_command
        self.get_neighbors = get_neighbors
        self.use_color = Colors.supports_color()

        # Initialize command registry
        self.registry = CommandRegistry()

        # Build command tree dynamically from registry
        self.command_tree = self.registry.build_command_tree()

        # Get base commands from registry (exclude internal/non-interactive commands)
        all_commands = self.registry.get_base_commands()
        # Filter out "#" (comment command - useful in scripts/API but not interactive CLI)
        self.base_commands = [cmd for cmd in all_commands if cmd != '#']
        # Add builtin CLI commands (not in registry)
        self.base_commands.extend(['exit', 'quit', 'q', 'clear', 'history', 'set'])
        # Add 'neighbor' keyword for discoverability (it's a prefix/filter, not a standalone command)
        # Valid syntax: "neighbor <IP> announce route ..." (neighbor filtering before commands)
        self.base_commands.append('neighbor')

        # Cache for neighbor IPs
        self._neighbor_cache: Optional[List[str]] = None
        self._cache_timeout = 300  # Refresh cache every 5 minutes (avoid repeated socket calls)
        self._cache_timestamp = 0
        self._cache_in_progress = False  # Prevent concurrent queries

        # Track state for single-TAB display on macOS libedit
        self.matches: List[str] = []
        self.match_metadata: Dict[str, CompletionItem] = {}  # Map completion value to metadata
        self.is_libedit = 'libedit' in readline.__doc__
        self.last_line = ''
        self.last_matches: List[str] = []

        # Try to get access to readline's rl_replace_line for line editing
        self._rl_replace_line = self._get_rl_replace_line()
        self._rl_forced_update_display = self._get_rl_forced_update_display()

    def _get_rl_replace_line(self) -> Optional[Callable]:
        """Try to get rl_replace_line function from readline library via ctypes"""
        try:
            # Try to load the readline library
            if sys.platform == 'darwin':
                # macOS uses libedit by default
                lib = ctypes.CDLL('/usr/lib/libedit.dylib')
                # libedit calls it rl_replace_line
                rl_replace_line = lib.rl_replace_line
            else:
                # Linux typically uses GNU readline
                lib = ctypes.CDLL('libreadline.so')
                rl_replace_line = lib.rl_replace_line

            # Set argument and return types
            rl_replace_line.argtypes = [ctypes.c_char_p, ctypes.c_int]
            rl_replace_line.restype = None
            return rl_replace_line
        except (OSError, AttributeError):
            return None

    def _get_rl_forced_update_display(self) -> Optional[Callable]:
        """Try to get rl_forced_update_display function from readline library via ctypes"""
        try:
            if sys.platform == 'darwin':
                lib = ctypes.CDLL('/usr/lib/libedit.dylib')
            else:
                lib = ctypes.CDLL('libreadline.so')

            rl_forced_update_display = lib.rl_forced_update_display
            rl_forced_update_display.argtypes = []
            rl_forced_update_display.restype = ctypes.c_int
            return rl_forced_update_display
        except (OSError, AttributeError):
            return None

    def complete(self, text: str, state: int) -> Optional[str]:
        """
        Readline completion function with auto-expansion of unambiguous tokens

        Args:
            text: Current word being completed
            state: Iteration state (0 for first match, increments for subsequent)

        Returns:
            Next matching completion or None (with space suffix if unambiguous)
        """
        try:
            # Get the full line buffer to understand context
            line = readline.get_line_buffer()
            begin = readline.get_begidx()
            end = readline.get_endidx()

            # Parse the line into tokens
            # Note: "?" key is bound to rl_complete (same as TAB) so it triggers
            # completion without appearing in the line buffer
            tokens = line[:begin].split()

            # Generate matches based on context
            if state == 0:
                # First call - try to auto-expand any unambiguous tokens
                expanded_prefix, expansions_made = self._try_auto_expand_tokens(tokens)

                if expansions_made and self._rl_replace_line:
                    # We have expansions and can modify the line directly
                    suffix = line[end:]  # Everything after the current word

                    # Get completions for current word in expanded context
                    current_matches = self._get_completions(expanded_prefix, text)

                    # Build the full replacement
                    prefix_str = ' '.join(expanded_prefix) + (' ' if expanded_prefix else '')

                    if len(current_matches) == 1:
                        # Single match - replace entire line with expanded version
                        new_line = prefix_str + current_matches[0] + ' ' + suffix
                        self._rl_replace_line(new_line.encode('utf-8'), 0)
                        if self._rl_forced_update_display:
                            self._rl_forced_update_display()
                        # Return empty list to signal completion is done
                        self.matches = []
                        return None
                    elif len(current_matches) > 1:
                        # Multiple matches - replace prefix but let user complete current word
                        new_line = prefix_str + text + suffix
                        self._rl_replace_line(new_line.encode('utf-8'), 0)
                        if self._rl_forced_update_display:
                            self._rl_forced_update_display()
                        # Now return completions for the current word
                        self.matches = current_matches
                    else:
                        # No matches after expansion - just expand the prefix
                        new_line = prefix_str + text + suffix
                        self._rl_replace_line(new_line.encode('utf-8'), 0)
                        if self._rl_forced_update_display:
                            self._rl_forced_update_display()
                        self.matches = []
                        return None

                # No expansion or can't modify line - generate matches for current token
                if not expansions_made or not self._rl_replace_line:
                    self.matches = self._get_completions(tokens, text)

                # macOS libedit: Display all matches on first TAB/? press
                # (GNU readline has built-in display via show-all-if-ambiguous)
                if self.is_libedit and len(self.matches) > 1:
                    # Check if this is a new completion (avoid repeating on subsequent TABs)
                    current_line = readline.get_line_buffer()
                    if current_line != self.last_line or self.matches != self.last_matches:
                        # Display matches with descriptions
                        self._display_matches_and_redraw(self.matches, line)
                        self.last_line = current_line
                        self.last_matches = self.matches.copy()

            # Return the next match
            try:
                match = self.matches[state]
                # Add space suffix for unambiguous completion (single match only)
                if len(self.matches) == 1 and state == 0 and not match.startswith('\b'):
                    return match + ' '
                return match
            except IndexError:
                return None
        except Exception:
            # If any exception occurs during completion (e.g., socket errors, JSON parsing),
            # silently fail and return no completions. This prevents readline from breaking.
            # Completion is a nice-to-have feature - don't let it crash the CLI.
            return None

    def _try_auto_expand_tokens(self, tokens: List[str]) -> Tuple[List[str], bool]:
        """
        Auto-expand unambiguous partial tokens

        Args:
            tokens: List of tokens to potentially expand

        Returns:
            Tuple of (expanded_tokens, expansions_made)
        """
        if not tokens:
            return ([], False)

        # Build expanded tokens by checking each token for unambiguous completion
        expanded_tokens = []
        current_context = []  # Tokens we've processed so far
        expansions_made = False

        for token in tokens:
            # Get completions for this token in the current context
            completions = self._get_completions(current_context, token)

            # If exactly one completion and it's different from the token, expand it
            if len(completions) == 1 and completions[0] != token:
                expanded_tokens.append(completions[0])
                current_context.append(completions[0])
                expansions_made = True
            else:
                # Multiple completions or exact match - keep as is
                expanded_tokens.append(token)
                current_context.append(token)

        return (expanded_tokens, expansions_made)

    def _display_matches_and_redraw(self, matches: List[str], current_line: str) -> None:
        """Display completion matches with descriptions (one per line) and redraw the prompt"""
        if not matches:
            return

        # Print newline before matches
        sys.stdout.write('\n')

        # Calculate column width for value (longest match + padding)
        max_len = max(len(m) for m in matches)
        value_width = min(max_len + 2, 25)  # Cap at 25 chars to leave room for descriptions

        # Print all matches one per line with descriptions
        for match in matches:
            metadata = self.match_metadata.get(match)
            value_str = match.ljust(value_width)

            # Get description (always present due to _add_completion_metadata)
            desc_str = metadata.description if metadata and metadata.description else ''

            # Color formatting if enabled
            if self.use_color and metadata:
                if metadata.item_type == 'neighbor':
                    # Cyan for neighbors
                    sys.stdout.write(f'{Colors.CYAN}{value_str}{Colors.RESET}')
                elif metadata.item_type == 'command':
                    # Yellow for commands
                    sys.stdout.write(f'{Colors.YELLOW}{value_str}{Colors.RESET}')
                else:
                    # Green for options/keywords
                    sys.stdout.write(f'{Colors.GREEN}{value_str}{Colors.RESET}')

                if desc_str:
                    sys.stdout.write(f'{Colors.DIM}{desc_str}{Colors.RESET}\n')
                else:
                    sys.stdout.write('\n')
            else:
                # No color
                if desc_str:
                    sys.stdout.write(f'{value_str}{desc_str}\n')
                else:
                    sys.stdout.write(f'{match}\n')

        # Redraw the prompt and current input
        formatter = OutputFormatter()
        prompt = formatter.format_prompt()

        sys.stdout.write(prompt + current_line)
        sys.stdout.flush()

    def _add_completion_metadata(
        self, value: str, description: Optional[str] = None, item_type: str = 'option'
    ) -> None:
        """Add metadata for a completion item"""
        self.match_metadata[value] = CompletionItem(value=value, description=description, item_type=item_type)

    def _get_completions(self, tokens: List[str], text: str) -> List[str]:
        """
        Get list of completions based on current context

        Args:
            tokens: Previously typed tokens
            text: Current partial token

        Returns:
            List of matching completions
        """
        # Clear previous metadata
        self.match_metadata.clear()

        # If no tokens yet, complete base commands
        if not tokens:
            matches = sorted([cmd for cmd in self.base_commands if cmd.startswith(text)])
            # Add metadata for base commands with descriptions
            for match in matches:
                desc = self.registry.get_command_description(match)
                self._add_completion_metadata(match, desc, 'command')
            return matches

        # Expand shortcuts in tokens using CommandShortcuts
        expanded_tokens = CommandShortcuts.expand_token_list(tokens.copy())

        # Handle "neighbor <ip> <command>" prefix transformations
        if len(expanded_tokens) >= 2 and expanded_tokens[0] == 'neighbor' and self._is_ip_address(expanded_tokens[1]):
            ip = expanded_tokens[1]

            # For "show", transform to "show neighbor <ip>" before completion
            if len(expanded_tokens) >= 3 and expanded_tokens[2] == 'show':
                # Transform: "neighbor 127.0.0.1 show ..." → "show neighbor 127.0.0.1 ..."
                rest = expanded_tokens[3:] if len(expanded_tokens) > 3 else []
                expanded_tokens = ['show', 'neighbor', ip] + rest

            # For "announce" and "withdraw", strip "neighbor <ip>" to complete at root level
            elif len(expanded_tokens) >= 3 and expanded_tokens[2] in ('announce', 'withdraw'):
                # Strip "neighbor <ip>" and continue completion from that command
                expanded_tokens = expanded_tokens[2:]

        # Check if we have "announce route <ip-prefix>" or "withdraw route <ip-prefix>"
        # In this case, suggest route attributes (next-hop, as-path, etc.)
        # This must come BEFORE _is_neighbor_command check (which would return base commands)
        if len(expanded_tokens) >= 3 and 'route' in expanded_tokens:
            try:
                route_idx = expanded_tokens.index('route')
                # Check if token after 'route' looks like IP/prefix
                if route_idx < len(expanded_tokens) - 1:
                    potential_prefix = expanded_tokens[route_idx + 1]
                    if self._is_ip_or_prefix(potential_prefix):
                        # We have "route <ip-prefix>", suggest route attributes
                        return self._complete_route_spec(expanded_tokens, text)
            except ValueError:
                pass

        # Special case: "announce route" - suggest "refresh" or "neighbor" keyword only
        # This must come BEFORE _is_neighbor_command check
        # Note: Do NOT suggest neighbor IPs here - they are for filtering and must come BEFORE "announce"
        # Correct syntax: "neighbor <IP> announce route <route-prefix> ..." NOT "announce route <neighbor-IP> ..."
        if len(expanded_tokens) >= 2 and expanded_tokens[-1] == 'route' and 'announce' in expanded_tokens:
            matches = []

            # Suggest "refresh" for "announce route refresh"
            if 'refresh'.startswith(text):
                matches.append('refresh')
                self._add_completion_metadata('refresh', 'Send route refresh request', 'command')

            # Suggest "neighbor" keyword for "neighbor <IP> announce route ..." filtering
            if 'neighbor'.startswith(text):
                matches.append('neighbor')
                desc = self.registry.get_option_description('neighbor')
                self._add_completion_metadata('neighbor', desc if desc else 'Target specific neighbor by IP', 'keyword')

            return sorted(matches)

        # Check if completing neighbor-targeted command
        if self._is_neighbor_command(expanded_tokens):
            return self._complete_neighbor_command(expanded_tokens, text)

        # Check for specific command patterns
        if len(expanded_tokens) >= 1:
            # Builtin CLI command: 'set encoding' / 'set display'
            if expanded_tokens[0] == 'set':
                if len(expanded_tokens) == 1:
                    # After 'set', suggest 'encoding' or 'display'
                    matches = []
                    if 'encoding'.startswith(text):
                        matches.append('encoding')
                        self._add_completion_metadata('encoding', 'Set API output encoding', 'option')
                    if 'display'.startswith(text):
                        matches.append('display')
                        self._add_completion_metadata('display', 'Set display format', 'option')
                    return matches
                elif len(expanded_tokens) == 2:
                    setting = expanded_tokens[1]
                    if setting in ('encoding', 'display'):
                        # After 'set encoding' or 'set display', suggest 'json' or 'text'
                        matches = []
                        if 'json'.startswith(text):
                            matches.append('json')
                            desc = 'JSON encoding' if setting == 'encoding' else 'Show raw JSON'
                            self._add_completion_metadata('json', desc, 'option')
                        if 'text'.startswith(text):
                            matches.append('text')
                            desc = 'Text encoding' if setting == 'encoding' else 'Format as tables'
                            self._add_completion_metadata('text', desc, 'option')
                        return matches
                # 'set' with other tokens - no more completions
                return []

        if len(expanded_tokens) >= 2:
            # Special case: 'show neighbor' can filter by IP even though neighbor=False
            if expanded_tokens[0] == 'show' and expanded_tokens[1] == 'neighbor':
                # After 'show neighbor', suggest options AND neighbor IPs
                neighbor_data = self._get_neighbor_data()

                # Get command tree options (summary, extensive, configuration)
                metadata = self.registry.get_command_metadata('show neighbor')
                options = list(metadata.options) if metadata and metadata.options else []

                # Add 'json' if command supports it
                if metadata and metadata.json_support and 'json' not in options:
                    options.append('json')

                # Add options with descriptions
                matches = []
                for opt in options:
                    if opt.startswith(text):
                        matches.append(opt)
                        desc = self.registry.get_option_description(opt)
                        self._add_completion_metadata(opt, desc, 'option')

                # Only add neighbor IPs if one isn't already specified
                # Example: "show neighbor" → suggest IPs, but "show neighbor 127.0.0.1" → don't suggest IPs again
                ip_already_specified = len(expanded_tokens) >= 3 and self._is_ip_address(expanded_tokens[2])

                if not ip_already_specified:
                    # Add neighbor IPs with descriptions
                    for ip, info in neighbor_data.items():
                        if ip.startswith(text):
                            matches.append(ip)
                            self._add_completion_metadata(ip, info, 'neighbor')

                return sorted(matches)

            # AFI/SAFI completion for eor and route refresh
            if expanded_tokens[-1] in ('eor', 'refresh'):
                # Check if this is "announce route refresh" or similar
                if len(expanded_tokens) >= 2 and expanded_tokens[-2] == 'route':
                    return self._complete_afi_safi(expanded_tokens, text)
                elif expanded_tokens[-1] == 'eor':
                    return self._complete_afi_safi(expanded_tokens, text)

            # Route specification hints - but NOT for withdraw route
            # (user needs to type IP/prefix first before any attributes)
            if expanded_tokens[-1] in ('route', 'ipv4', 'ipv6'):
                # Check if this is "withdraw route" or "neighbor X withdraw route"
                if expanded_tokens[-1] == 'route':
                    # Look backwards for "withdraw" command (but not "announce" - handled above)
                    if 'withdraw' in expanded_tokens:
                        # Don't auto-complete after withdraw route commands
                        # User must type IP/prefix first
                        return []
                return self._complete_route_spec(expanded_tokens, text)

            # Neighbor filter completion
            if 'neighbor' in expanded_tokens and self._is_ip_address(expanded_tokens[-1]):
                return self._complete_neighbor_filters(text)

        # Navigate command tree
        current_level = self.command_tree

        for i, token in enumerate(expanded_tokens):
            if isinstance(current_level, dict):
                if token in current_level:
                    current_level = current_level[token]
                elif '__options__' in current_level:
                    # At a command with options
                    options = current_level['__options__']
                    if isinstance(options, list):
                        matches = []
                        for opt in options:
                            if opt.startswith(text):
                                matches.append(opt)
                                desc = self.registry.get_option_description(opt)
                                self._add_completion_metadata(opt, desc, 'option')
                        return sorted(matches)
                else:
                    # Token not in tree, try partial match
                    matches = [cmd for cmd in current_level.keys() if cmd.startswith(token) and cmd != '__options__']

                    # Filter out legacy hyphenated commands
                    if 'announce' in expanded_tokens[:i]:
                        matches = [m for m in matches if m != 'route-refresh']

                    if matches and i == len(expanded_tokens) - 1:
                        # Last token being completed - these are subcommands
                        # Build full command path for description lookup
                        cmd_prefix = ' '.join(expanded_tokens[:i]) + ' ' if i > 0 else ''
                        for match in matches:
                            full_cmd = cmd_prefix + match
                            desc = self.registry.get_command_description(full_cmd.strip())
                            self._add_completion_metadata(match, desc, 'command')
                        return sorted(matches)
                    return []
            elif isinstance(current_level, list):
                # At a leaf node (list of options)
                matches = []
                for opt in current_level:
                    if opt.startswith(text):
                        matches.append(opt)
                        desc = self.registry.get_option_description(opt)
                        self._add_completion_metadata(opt, desc, 'option')
                return sorted(matches)

        # After navigating, see what's available at current level
        if isinstance(current_level, dict):
            matches = [cmd for cmd in current_level.keys() if cmd.startswith(text) and cmd != '__options__']

            # Filter out legacy hyphenated commands (e.g., "route-refresh" when "route" exists)
            # This keeps CLI clean and user-friendly
            filtered_matches = []
            for match in matches:
                # Skip if this is a hyphenated command and we have "announce route" in context
                if '-' in match and 'announce' in expanded_tokens:
                    # Check if this is "route-refresh" - skip it
                    if match == 'route-refresh':
                        continue
                filtered_matches.append(match)
            matches = filtered_matches

            # Add metadata for commands with descriptions
            # Build full command path for description lookup
            cmd_prefix = ' '.join(expanded_tokens) + ' ' if expanded_tokens else ''
            for match in matches:
                full_cmd = (cmd_prefix + match).strip()
                desc = self.registry.get_command_description(full_cmd)
                self._add_completion_metadata(match, desc, 'command')

            # Add options if available
            if '__options__' in current_level:
                options = current_level['__options__']
                if isinstance(options, list):
                    for opt in options:
                        if opt.startswith(text):
                            matches.append(opt)
                            desc = self.registry.get_option_description(opt)
                            self._add_completion_metadata(opt, desc, 'option')

            return sorted(matches)
        elif isinstance(current_level, list):
            matches = []
            for opt in current_level:
                if opt.startswith(text):
                    matches.append(opt)
                    desc = self.registry.get_option_description(opt)
                    self._add_completion_metadata(opt, desc, 'option')
            return sorted(matches)

        return []

    def _is_neighbor_command(self, tokens: List[str]) -> bool:
        """Check if command targets a specific neighbor using registry metadata"""
        if not tokens:
            return False

        # Try progressively longer command prefixes to find a match
        # This handles multi-word commands like "flush adj-rib out"
        for length in range(len(tokens), 0, -1):
            potential_cmd = ' '.join(tokens[:length])
            metadata = self.registry.get_command_metadata(potential_cmd)
            if metadata and metadata.neighbor_support:
                return True

        # Fallback: check if first token suggests neighbor targeting
        return tokens[0] in ('neighbor', 'teardown')

    def _complete_neighbor_command(self, tokens: List[str], text: str) -> List[str]:
        """Complete neighbor-targeted commands"""
        # Check if we should complete neighbor IP
        last_token = tokens[-1] if tokens else ''

        # Check if we're at the end of a complete command (ready for neighbor spec)
        # This handles both simple commands (teardown) and multi-word commands (flush adj-rib out)
        command_str = ' '.join(tokens)
        metadata = self.registry.get_command_metadata(command_str)

        if metadata and metadata.neighbor_support:
            # We're at the end of a recognized neighbor-targeted command
            matches = []
            if 'neighbor'.startswith(text):
                matches.append('neighbor')
                desc = self.registry.get_option_description('neighbor')
                self._add_completion_metadata('neighbor', desc, 'keyword')

            # Add neighbor IPs with descriptions
            neighbor_data = self._get_neighbor_data()
            for ip, info in neighbor_data.items():
                if ip.startswith(text):
                    matches.append(ip)
                    self._add_completion_metadata(ip, info, 'neighbor')

            return sorted(matches)

        # If last token is 'neighbor', complete with IPs
        if last_token == 'neighbor':
            neighbor_data = self._get_neighbor_data()
            matches = []
            for ip, info in neighbor_data.items():
                if ip.startswith(text):
                    matches.append(ip)
                    self._add_completion_metadata(ip, info, 'neighbor')
            return sorted(matches)

        # If last token is an IP, only suggest: announce, withdraw, show
        # "show" will be rewritten to "show neighbor <ip>" before sending to API
        if self._is_ip_address(last_token):
            matches = []

            # Only these three commands are valid after "neighbor <ip>"
            allowed_commands = ['announce', 'withdraw', 'show']

            for cmd in allowed_commands:
                if cmd.startswith(text):
                    matches.append(cmd)
                    desc = self.registry.get_command_description(cmd)
                    self._add_completion_metadata(cmd, desc if desc else '', 'command')

            return sorted(matches)

        return []

    def _complete_neighbor_filters(self, text: str) -> List[str]:
        """Complete neighbor filter keywords"""
        filters = self.registry.get_neighbor_filters()
        matches = sorted([f for f in filters if f.startswith(text)])
        # Add descriptions for filter keywords
        for match in matches:
            desc = self.registry.get_option_description(match)
            self._add_completion_metadata(match, desc, 'keyword')
        return matches

    def _complete_afi_safi(self, tokens: List[str], text: str) -> List[str]:
        """Complete AFI/SAFI values for eor and route refresh"""
        # Get AFI values first, then SAFI
        afi_values = self.registry.get_afi_values()

        # Check if we've already typed an AFI
        potential_afi = tokens[-2] if len(tokens) >= 2 and tokens[-2] in afi_values else None

        if potential_afi:
            # Complete SAFI for the given AFI
            safi_values = self.registry.get_safi_values(potential_afi)
            matches = sorted([s for s in safi_values if s.startswith(text)])
            # Add descriptions for SAFI values
            for match in matches:
                desc = f'SAFI for {potential_afi}'
                self._add_completion_metadata(match, desc, 'keyword')
            return matches
        else:
            # Complete AFI
            matches = sorted([a for a in afi_values if a.startswith(text)])
            # Add descriptions for AFI values
            for match in matches:
                desc = 'Address Family Identifier'
                self._add_completion_metadata(match, desc, 'keyword')
            return matches

    def _complete_route_spec(self, tokens: List[str], text: str) -> List[str]:
        """Complete route specification keywords"""
        keywords = self.registry.get_route_keywords()
        matches = sorted([k for k in keywords if k.startswith(text)])
        # Add descriptions for route keywords
        for match in matches:
            desc = 'Route specification parameter'
            self._add_completion_metadata(match, desc, 'keyword')
        return matches

    def _is_ip_address(self, token: str) -> bool:
        """Check if token looks like an IP address"""
        # Simple check for IPv4 or IPv6
        ipv4_pattern = r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$'
        ipv6_pattern = r'^[0-9a-fA-F:]+$'
        return bool(re.match(ipv4_pattern, token) or (': ' in token or re.match(ipv6_pattern, token)))

    def _is_ip_or_prefix(self, token: str) -> bool:
        """Check if token looks like an IP address or CIDR prefix"""
        # Check for IPv4/prefix (e.g., 1.2.3.4 or 10.0.0.0/24)
        ipv4_pattern = r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}(/\d{1,2})?$'
        # Check for IPv6/prefix (e.g., 2001:db8::1 or 2001:db8::/32)
        ipv6_pattern = r'^[0-9a-fA-F:]+(/\d{1,3})?$'
        return bool(re.match(ipv4_pattern, token) or ((':' in token) and re.match(ipv6_pattern, token)))

    def _get_neighbor_ips(self) -> List[str]:
        """
        Get list of neighbor IPs for completion (with caching)

        Returns:
            List of neighbor IP addresses
        """
        import time

        # Check if cache is still valid
        current_time = time.time()
        if self._neighbor_cache is not None and (current_time - self._cache_timestamp) < self._cache_timeout:
            return self._neighbor_cache

        # Prevent concurrent queries (avoid socket connection issues)
        if self._cache_in_progress:
            return self._neighbor_cache if self._neighbor_cache is not None else []

        self._cache_in_progress = True

        try:
            # Try to fetch neighbor IPs from ExaBGP
            neighbor_ips = []

            # Use provided get_neighbors callback if available
            if self.get_neighbors:
                try:
                    neighbor_ips = self.get_neighbors()
                except Exception:
                    pass
            else:
                # Try to query ExaBGP via 'show neighbor json'
                try:
                    response = self.send_command('show neighbor json')
                    if response and response != 'Command sent' and not response.startswith('Error:'):
                        # Parse JSON response
                        # Clean up response - remove 'done' marker if present
                        json_text = response
                        if 'done' in json_text:
                            # Split by 'done' and take first part
                            json_text = json_text.split('done')[0].strip()

                        neighbors = json.loads(json_text)
                        if isinstance(neighbors, list):
                            for neighbor in neighbors:
                                if isinstance(neighbor, dict):
                                    # Try different possible locations for peer address
                                    peer_addr = None

                                    # Format 1: peer-address at top level
                                    if 'peer-address' in neighbor:
                                        peer_addr = neighbor['peer-address']
                                    # Format 2: remote-addr at top level
                                    elif 'remote-addr' in neighbor:
                                        peer_addr = neighbor['remote-addr']
                                    # Format 3: nested in 'peer' object (ExaBGP 5.x format)
                                    elif 'peer' in neighbor and isinstance(neighbor['peer'], dict):
                                        peer_obj = neighbor['peer']
                                        if 'address' in peer_obj:
                                            peer_addr = peer_obj['address']
                                        elif 'ip' in peer_obj:
                                            peer_addr = peer_obj['ip']

                                    if peer_addr:
                                        neighbor_ips.append(str(peer_addr))
                except Exception:
                    # Silently fail - neighbor completion is optional
                    pass

            # Update cache
            self._neighbor_cache = neighbor_ips
            self._cache_timestamp = current_time

            return neighbor_ips
        finally:
            self._cache_in_progress = False

    def _get_neighbor_data(self) -> Dict[str, str]:
        """
        Get neighbor IPs with descriptions (AS, state) for completion

        Returns:
            Dict mapping neighbor IP to description string
        """
        neighbor_data: Dict[str, str] = {}

        # Try to fetch detailed neighbor information
        try:
            response = self.send_command('show neighbor json')
            if response and response != 'Command sent' and not response.startswith('Error:'):
                # Parse JSON response
                json_text = response
                if 'done' in json_text:
                    json_text = json_text.split('done')[0].strip()

                neighbors = json.loads(json_text)
                if isinstance(neighbors, list):
                    for neighbor in neighbors:
                        if isinstance(neighbor, dict):
                            # Extract peer address
                            peer_addr = None
                            if 'peer-address' in neighbor:
                                peer_addr = neighbor['peer-address']
                            elif 'remote-addr' in neighbor:
                                peer_addr = neighbor['remote-addr']
                            elif 'peer' in neighbor and isinstance(neighbor['peer'], dict):
                                peer_obj = neighbor['peer']
                                peer_addr = peer_obj.get('address') or peer_obj.get('ip')

                            if peer_addr:
                                # Build description from neighbor info
                                peer_as = neighbor.get('peer-as', 'unknown')
                                state = neighbor.get('state', 'unknown')

                                # Format: (neighbor, AS65000, ESTABLISHED)
                                desc = f'(neighbor, AS{peer_as}, {state})'
                                neighbor_data[str(peer_addr)] = desc
        except Exception:
            # Silently fail - just return IPs without descriptions
            pass

        # If no data from JSON, fall back to IPs only
        if not neighbor_data:
            for ip in self._get_neighbor_ips():
                neighbor_data[ip] = '(neighbor)'

        return neighbor_data

    def invalidate_cache(self) -> None:
        """Invalidate neighbor IP cache (call after topology changes)"""
        self._neighbor_cache = None
        self._cache_timestamp = 0


class OutputFormatter:
    """Format and colorize output"""

    def __init__(self, use_color: bool = True):
        self.use_color = use_color and Colors.supports_color()

    def format_prompt(self, hostname: str = 'exabgp') -> str:
        """Format the interactive prompt"""
        if self.use_color:
            return f'{Colors.BOLD}{Colors.GREEN}{hostname}{Colors.RESET}{Colors.BOLD}>{Colors.RESET} '
        return f'{hostname}> '

    def format_error(self, message: str) -> str:
        """Format error message"""
        if self.use_color:
            return f'{Colors.BOLD}{Colors.RED}Error:{Colors.RESET} {message}'
        return f'Error: {message}'

    def format_warning(self, message: str) -> str:
        """Format warning message"""
        if self.use_color:
            return f'{Colors.BOLD}{Colors.YELLOW}Warning:{Colors.RESET} {message}'
        return f'Warning: {message}'

    def format_success(self, message: str) -> str:
        """Format success message"""
        if self.use_color:
            return f'{Colors.BOLD}{Colors.GREEN}✓{Colors.RESET} {message}'
        return f'✓ {message}'

    def format_info(self, message: str) -> str:
        """Format info message"""
        if self.use_color:
            return f'{Colors.BOLD}{Colors.CYAN}Info:{Colors.RESET} {message}'
        return f'Info: {message}'

    def _format_json_as_text(self, data: Union[Dict, List, str, int, bool, None]) -> str:
        """Convert JSON data to human-readable text format with tables

        Uses only standard library to format data as tables or key-value pairs.
        """
        if data is None:
            return 'null'

        if isinstance(data, bool):
            return 'true' if data else 'false'

        if isinstance(data, (str, int, float)):
            return str(data)

        # List of objects - format as table
        if isinstance(data, list):
            if not data:
                return '(empty list)'

            # Check if all items are dictionaries (tabular data)
            if all(isinstance(item, dict) for item in data):
                return self._format_table_from_list(data)

            # List of simple values
            if all(isinstance(item, (str, int, float, bool, type(None))) for item in data):
                return '\n'.join(f'  - {item}' for item in data)

            # Mixed list - format each item
            lines = []
            for i, item in enumerate(data):
                lines.append(f'[{i}]:')
                lines.append(self._indent(self._format_json_as_text(item), 2))
            return '\n'.join(lines)

        # Single object - format as key-value pairs
        if isinstance(data, dict):
            return self._format_dict(data)

        return str(data)

    def _format_table_from_list(self, data: List[Dict]) -> str:
        """Format list of dictionaries as ASCII table or key-value pairs for complex data"""
        if not data:
            return '(empty)'

        # Check if data has complex nested structures (dicts/lists in values)
        has_complex_values = False
        for item in data:
            for value in item.values():
                if isinstance(value, (dict, list)):
                    # Check if dict/list has substantial content
                    if isinstance(value, dict) and len(value) > 3:
                        has_complex_values = True
                        break
                    if isinstance(value, list) and (len(value) > 3 or any(isinstance(v, dict) for v in value)):
                        has_complex_values = True
                        break
            if has_complex_values:
                break

        # If data is complex, format as sections instead of table
        if has_complex_values:
            return self._format_list_as_sections(data)

        # Collect all keys across all objects
        all_keys = []
        for item in data:
            for key in item.keys():
                if key not in all_keys:
                    all_keys.append(key)

        # Calculate column widths (with max width limit to prevent ultra-wide tables)
        MAX_COL_WIDTH = 40
        col_widths = {}
        for key in all_keys:
            # Start with header width
            col_widths[key] = len(str(key))
            # Check all values
            for item in data:
                if key in item:
                    value_str = self._format_value(item[key])
                    # Cap at max width to keep table readable
                    col_widths[key] = min(max(col_widths[key], len(value_str)), MAX_COL_WIDTH)

        # Build header
        header_parts = []
        separator_parts = []
        for key in all_keys:
            width = col_widths[key]
            header_parts.append(str(key).ljust(width))
            separator_parts.append('-' * width)

        lines = []
        lines.append('  '.join(header_parts))
        lines.append('  '.join(separator_parts))

        # Build rows
        for item in data:
            row_parts = []
            for key in all_keys:
                width = col_widths[key]
                value = item.get(key, '')
                value_str = self._format_value(value)
                # Truncate if too long
                if len(value_str) > MAX_COL_WIDTH:
                    value_str = value_str[: MAX_COL_WIDTH - 3] + '...'
                row_parts.append(value_str.ljust(width))
            lines.append('  '.join(row_parts))

        return '\n'.join(lines)

    def _format_list_as_sections(self, data: List[Dict]) -> str:
        """Format list of complex dictionaries as separate sections"""
        lines = []
        for i, item in enumerate(data):
            if i > 0:
                lines.append('')  # Blank line between sections

            # Extract identifier from the data
            identifier = self._extract_identifier(item)

            if identifier:
                lines.append(f'=== {identifier} ===')
            else:
                lines.append(f'=== Item {i + 1} ===')

            lines.append(self._format_dict(item))

        return '\n'.join(lines)

    def _extract_identifier(self, item: Dict) -> Optional[str]:
        """Extract a meaningful identifier from a dictionary

        Tries various strategies to find a good identifier:
        1. Nested keys for specific data types (e.g., neighbor data)
        2. Common top-level keys
        3. First string/number value found
        """
        # Strategy 1: Check for nested paths that commonly identify objects
        nested_paths = [
            ['peer', 'address'],  # Neighbor data
            ['local', 'address'],  # Alternative neighbor identifier
            ['neighbor', 'address'],  # Another neighbor pattern
            ['address', 'peer'],  # Reversed pattern
        ]

        for path in nested_paths:
            value = self._get_nested_value(item, path)
            if value is not None:
                return str(value)

        # Strategy 2: Check common top-level identifier keys
        top_level_keys = ['peer-address', 'address', 'name', 'id', 'neighbor', 'route', 'prefix', 'key']

        for key in top_level_keys:
            if key in item:
                value = item[key]
                if value is not None and not isinstance(value, (dict, list)):
                    return str(value)

        # Strategy 3: If item has 'peer' or 'local' dict, try to get address from it
        for container_key in ['peer', 'local', 'remote']:
            if container_key in item and isinstance(item[container_key], dict):
                container = item[container_key]
                for addr_key in ['address', 'ip', 'host', 'peer-address']:
                    if addr_key in container:
                        value = container[addr_key]
                        if value is not None and not isinstance(value, (dict, list)):
                            return str(value)

        # Strategy 4: Find first non-complex value as fallback
        for key, value in item.items():
            if value is not None and not isinstance(value, (dict, list)):
                # Skip internal/metadata keys
                if not key.startswith('_') and key not in ['state', 'status', 'type', 'duration']:
                    return f'{key}={value}'

        return None

    def _get_nested_value(self, data: Dict, path: List[str]) -> Optional[str]:
        """Get value from nested dictionary using path list

        Args:
            data: Dictionary to search
            path: List of keys to traverse (e.g., ['peer', 'address'])

        Returns:
            Value if found, None otherwise
        """
        current = data
        for key in path:
            if not isinstance(current, dict) or key not in current:
                return None
            current = current[key]

        # Return only if it's a simple value (not dict/list)
        if current is not None and not isinstance(current, (dict, list)):
            return current
        return None

    def _format_dict(self, data: Dict) -> str:
        """Format dictionary as key-value pairs"""
        if not data:
            return '(empty)'

        # Separate simple keys from complex keys
        simple_keys = []
        complex_keys = []

        for key, value in data.items():
            if isinstance(value, (dict, list)):
                complex_keys.append(key)
            else:
                simple_keys.append(key)

        # Sort both groups alphabetically
        simple_keys.sort()
        complex_keys.sort()

        # Combine: simple keys first, then complex keys
        sorted_keys = simple_keys + complex_keys

        # Calculate max key width for alignment
        max_key_width = max(len(str(k)) for k in sorted_keys) if sorted_keys else 0

        lines = []
        for key in sorted_keys:
            value = data[key]
            key_str = str(key).ljust(max_key_width)

            # Format value based on type
            if isinstance(value, dict):
                # Nested dict - indent on new lines
                lines.append(f'{key_str}:')
                lines.append(self._indent(self._format_dict(value), 2))
            elif isinstance(value, list):
                # List - format based on content
                if not value:
                    lines.append(f'{key_str}: (empty list)')
                elif all(isinstance(item, (str, int, float, bool, type(None))) for item in value):
                    # Simple list - show inline or multiline
                    if len(value) <= 3:
                        lines.append(f'{key_str}: [{", ".join(str(v) for v in value)}]')
                    else:
                        lines.append(f'{key_str}:')
                        for item in value:
                            lines.append(f'  - {item}')
                else:
                    # Complex list
                    lines.append(f'{key_str}:')
                    lines.append(self._indent(self._format_json_as_text(value), 2))
            else:
                # Simple value
                lines.append(f'{key_str}: {self._format_value(value)}')

        return '\n'.join(lines)

    def _format_value(self, value: Union[str, int, float, bool, None, Dict, List]) -> str:
        """Format a single value for display"""
        if value is None:
            return 'null'
        if isinstance(value, bool):
            return 'true' if value else 'false'
        if isinstance(value, (dict, list)):
            # Compact representation for nested structures in tables
            return json.dumps(value, ensure_ascii=False)
        return str(value)

    def _indent(self, text: str, spaces: int) -> str:
        """Indent all lines in text by given number of spaces"""
        indent_str = ' ' * spaces
        return '\n'.join(indent_str + line for line in text.split('\n'))

    def format_command_output(self, output: str, display_mode: str = 'json') -> str:
        """Format command output with colors and pretty-print JSON or convert to text tables

        Args:
            output: Raw output from command
            display_mode: 'json' for pretty JSON, 'text' for human-readable tables
        """
        if not output:
            return output

        # Strip common response markers
        output_stripped = output.strip()

        # Remove 'done' marker if present (ExaBGP API response suffix)
        if output_stripped.endswith('done'):
            output_stripped = output_stripped[:-4].strip()

        # Try to parse and pretty-print as JSON (single object/array)
        if output_stripped.startswith('{') or output_stripped.startswith('['):
            try:
                # Parse JSON
                parsed = json.loads(output_stripped)

                # Display mode: text - convert JSON to human-readable tables
                if display_mode == 'text':
                    return self._format_json_as_text(parsed)

                # Display mode: json - show pretty-printed JSON
                # Pretty-print with 2-space indent
                pretty_json = json.dumps(parsed, indent=2, ensure_ascii=False)

                # Apply color if enabled
                if self.use_color:
                    # Colorize the JSON output
                    colored_lines = []
                    for line in pretty_json.split('\n'):
                        colored_lines.append(f'{Colors.CYAN}{line}{Colors.RESET}')
                    return '\n'.join(colored_lines)
                else:
                    return pretty_json
            except (json.JSONDecodeError, ValueError):
                # Not valid JSON, try line-by-line parsing for multiple JSON objects
                pass

        # Try line-by-line JSON parsing (for multiple JSON objects on separate lines)
        lines = output_stripped.split('\n')
        formatted_lines = []
        all_json = True

        for line in lines:
            line_stripped = line.strip()
            if not line_stripped:
                formatted_lines.append('')
                continue

            if line_stripped.startswith('{') or line_stripped.startswith('['):
                try:
                    parsed = json.loads(line_stripped)
                    pretty_json = json.dumps(parsed, indent=2, ensure_ascii=False)
                    if self.use_color:
                        colored = '\n'.join(
                            f'{Colors.CYAN}{json_line}{Colors.RESET}' for json_line in pretty_json.split('\n')
                        )
                        formatted_lines.append(colored)
                    else:
                        formatted_lines.append(pretty_json)
                except (json.JSONDecodeError, ValueError):
                    all_json = False
                    break
            else:
                all_json = False
                break

        if all_json and formatted_lines:
            return '\n'.join(formatted_lines)

        # Not JSON or parsing failed - use regular formatting
        if not self.use_color:
            return output

        lines = output.split('\n')
        formatted = []

        for line in lines:
            # Colorize JSON-like output (for partial/invalid JSON)
            if line.strip().startswith('{') or line.strip().startswith('['):
                formatted.append(f'{Colors.CYAN}{line}{Colors.RESET}')
            # Colorize IP addresses
            elif any(c in line for c in ['.', ':']):
                # Simple IP highlighting (can be improved)
                formatted.append(line)
            else:
                formatted.append(line)

        return '\n'.join(formatted)

    def format_table(self, headers: List[str], rows: List[List[str]]) -> str:
        """Format data as a table"""
        if not headers or not rows:
            return ''

        # Calculate column widths
        col_widths = [len(h) for h in headers]
        for row in rows:
            for i, cell in enumerate(row):
                if i < len(col_widths):
                    col_widths[i] = max(col_widths[i], len(str(cell)))

        # Build table
        lines = []

        # Header
        if self.use_color:
            header_line = ' │ '.join(f'{Colors.BOLD}{h.ljust(w)}{Colors.RESET}' for h, w in zip(headers, col_widths))
        else:
            header_line = ' | '.join(h.ljust(w) for h, w in zip(headers, col_widths))

        lines.append(header_line)

        # Separator
        sep_char = '─' if self.use_color else '-'
        lines.append(
            '─┼─'.join(sep_char * w for w in col_widths) if self.use_color else '-+-'.join('-' * w for w in col_widths)
        )

        # Rows
        for row in rows:
            line = ' │ ' if self.use_color else ' | '
            line = line.join(str(cell).ljust(w) for cell, w in zip(row, col_widths))
            lines.append(line)

        return '\n'.join(lines)


class InteractiveCLI:
    """Interactive REPL for ExaBGP commands"""

    def __init__(
        self,
        send_command: Callable[[str], str],
        history_file: Optional[str] = None,
        daemon_uuid: Optional[str] = None,
    ):
        """
        Initialize interactive CLI

        Args:
            send_command: Function to send commands to ExaBGP
            history_file: Path to save command history
            daemon_uuid: Optional daemon UUID for connection message
        """
        self.send_command = send_command
        self.formatter = OutputFormatter()
        self.completer = CommandCompleter(send_command)
        self.running = True
        self.daemon_uuid = daemon_uuid
        self.output_encoding = 'json'  # API encoding format ('json' or 'text')
        self.display_mode = 'text'  # Display mode ('json' or 'text')

        # Setup history file
        if history_file is None:
            home = os.path.expanduser('~')
            history_file = os.path.join(home, '.exabgp_history')

        self.history_file = history_file
        self._setup_readline()

    def _setup_readline(self) -> None:
        """Configure readline for history and completion"""
        # Set up completion
        readline.set_completer(self.completer.complete)

        # Configure TAB completion behavior
        # Note: macOS uses libedit, Linux uses GNU readline - both supported
        if 'libedit' in readline.__doc__:
            # macOS libedit configuration
            # First, enable emacs mode to ensure arrow keys work properly
            readline.parse_and_bind('bind -e')  # Use emacs key bindings
            # Explicitly bind arrow keys for history navigation
            readline.parse_and_bind('bind ^[[A ed-prev-history')  # Up arrow
            readline.parse_and_bind('bind ^[[B ed-next-history')  # Down arrow
            readline.parse_and_bind('bind ^[[C ed-next-char')  # Right arrow
            readline.parse_and_bind('bind ^[[D ed-prev-char')  # Left arrow
            # Bind completion keys
            readline.parse_and_bind('bind ^I rl_complete')  # TAB key
            readline.parse_and_bind('bind ? rl_complete')  # ? key (help completion)
            # libedit doesn't support show-all-if-ambiguous, so we modify the completer
            # to return all matches at once (handled in complete() method)
        else:
            # GNU readline configuration
            readline.parse_and_bind('tab: complete')
            readline.parse_and_bind('?: complete')  # ? key (help completion)
            # Show all completions immediately (don't require double-TAB)
            readline.parse_and_bind('set show-all-if-ambiguous on')
            # Show completions on first TAB even if there are many matches
            readline.parse_and_bind('set completion-query-items -1')

        # Set up delimiters (what counts as word boundaries)
        readline.set_completer_delims(' \t\n')

        # Load history
        if os.path.exists(self.history_file):
            try:
                readline.read_history_file(self.history_file)
            except Exception:
                pass

        # Set history size
        readline.set_history_length(1000)

        # Save history on exit
        atexit.register(self._save_history)

    def _save_history(self) -> None:
        """Save command history to file"""
        try:
            readline.write_history_file(self.history_file)
        except Exception:
            pass

    def run(self) -> None:
        """Run the interactive REPL"""
        self._print_banner()

        while self.running:
            try:
                # Display prompt and read command
                prompt = self.formatter.format_prompt()
                line = input(prompt).strip()

                # Check if background thread signaled shutdown
                if not self.running:
                    break

                # Skip empty lines
                if not line:
                    continue

                # Handle built-in REPL commands
                if self._handle_builtin(line):
                    continue

                # Send to ExaBGP
                self._execute_command(line)

            except EOFError:
                # Ctrl+D pressed
                print()  # Newline after ^D
                self._quit()
                break
            except KeyboardInterrupt:
                # Ctrl+C pressed OR signal from background thread
                if not self.running:
                    # Signal from background thread - exit gracefully
                    print()  # Newline
                    break
                else:
                    # User pressed Ctrl+C - quit normally
                    print()  # Newline after ^C
                    self._quit()
                    break
            except Exception as exc:
                print(self.formatter.format_error(f'Unexpected error: {exc}'))

    def _print_banner(self) -> None:
        """Print welcome banner with ASCII art and version"""
        from exabgp.version import version as exabgp_version

        banner = rf"""
╔══════════════════════════════════════════════════════════╗
║ ___________             __________  __________________   ║
║ \_   _____/__  ________ \______   \/  _____/\______   \  ║
║  |    __)_\  \/  /\__  \ |    |  _/   \  ___ |     ___/  ║
║  |        \>    <  / __ \|    |   \    \_\  \|    |      ║
║ /_________/__/\__\(______/________/\________/|____|      ║
║                                                          ║
║  Version: {exabgp_version:<46} ║
╚══════════════════════════════════════════════════════════╝
"""
        if self.formatter.use_color:
            print(f'{Colors.BOLD}{Colors.CYAN}{banner}{Colors.RESET}', end='')
        else:
            print(banner, end='')

        # Print connection message if daemon UUID is available
        if self.daemon_uuid:
            conn_msg = f'✓ Connected to ExaBGP daemon (UUID: {self.daemon_uuid})'
            if self.formatter.use_color:
                print(f'{Colors.GREEN}{conn_msg}{Colors.RESET}')
            else:
                print(conn_msg)
        print()

        # Print usage instructions
        help_text = """Type 'help' for available commands
Type 'exit' or press Ctrl+D/Ctrl+C to quit
Tab completion and command history enabled
"""
        if self.formatter.use_color:
            print(f'{Colors.DIM}{help_text}{Colors.RESET}')
        else:
            print(help_text)

    def _handle_builtin(self, line: str) -> bool:
        """
        Handle REPL built-in commands

        Args:
            line: Command line

        Returns:
            True if command was handled, False otherwise
        """
        tokens = line.split()
        if not tokens:
            return True

        cmd = tokens[0].lower()

        if cmd in ('exit', 'quit', 'q'):
            self._quit()
            return True

        if cmd == 'clear':
            # Clear screen
            os.system('clear' if os.name != 'nt' else 'cls')
            return True

        if cmd == 'history':
            # Show command history
            self._show_history()
            return True

        if cmd == 'set' and len(tokens) >= 3:
            setting = tokens[1].lower()
            value = tokens[2].lower()

            if setting == 'encoding':
                # Set API output encoding: 'set encoding json' or 'set encoding text'
                if value in ('json', 'text'):
                    self.output_encoding = value
                    print(self.formatter.format_info(f'API output encoding set to {value}'))
                else:
                    print(self.formatter.format_error(f"Invalid encoding '{value}'. Use 'json' or 'text'."))
                return True

            elif setting == 'display':
                # Set display mode: 'set display json' or 'set display text'
                if value in ('json', 'text'):
                    self.display_mode = value
                    if value == 'text':
                        print(self.formatter.format_info('Display mode set to text (JSON will be formatted as tables)'))
                    else:
                        print(self.formatter.format_info('Display mode set to json (raw JSON display)'))
                else:
                    print(self.formatter.format_error(f"Invalid display '{value}'. Use 'json' or 'text'."))
                return True

        # Not a builtin
        return False

    def _execute_command(self, command: str) -> None:
        """
        Execute a command and display the result

        Args:
            command: Command to execute
        """
        try:
            # Check if command has explicit encoding override (json/text at end)
            tokens = command.split()
            override_encoding = None

            if tokens and tokens[-1].lower() in ('json', 'text'):
                override_encoding = tokens[-1].lower()
                # Strip override keyword from command
                command = ' '.join(tokens[:-1])

            # Translate CLI-friendly syntax to API syntax
            # "announce route refresh" -> "announce route-refresh"
            command = command.replace('route refresh', 'route-refresh')

            # Transform "neighbor <ip> show ..." to "show neighbor <ip> ..."
            # Pattern: neighbor <IP> show [options]
            import re

            neighbor_show_pattern = r'^neighbor\s+(\S+)\s+show\s*(.*)$'
            match = re.match(neighbor_show_pattern, command)
            if match:
                ip = match.group(1)
                rest = match.group(2).strip()
                command = f'show neighbor {ip} {rest}'.strip()

            # Determine which encoding to use (override takes precedence)
            encoding_to_use = override_encoding if override_encoding else self.output_encoding

            # Append encoding keyword to command before sending to daemon
            command_with_encoding = f'{command} {encoding_to_use}'

            result = self.send_command(command_with_encoding)

            # Check for socket/timeout errors
            if result and result.startswith('Error: '):
                # Socket write failed or timeout - show error without "Command sent"
                print(self.formatter.format_error(result[7:]))  # Strip "Error: " prefix
                return

            # Socket write succeeded - show immediate feedback
            print(self.formatter.format_success('Command sent'))

            # Format and display daemon response
            result_stripped = result.strip()

            # Check for success with no data FIRST (before formatting which may print "done")
            # Empty response or "done" means command was accepted
            if not result_stripped or result_stripped in ('done', 'done\nerror\n'):
                # Command succeeded but no output - show success confirmation
                print(self.formatter.format_success('Command accepted'))
                return

            # Check if response ends with API error marker
            is_error = result_stripped.endswith('error')

            if is_error:
                # Split on rightmost 'error' marker to extract error details
                parts = result_stripped.rsplit('error', 1)
                error_content = parts[0].strip() if len(parts) > 1 else ''

                if error_content:
                    # Try to parse as JSON error
                    try:
                        import json

                        error_data = json.loads(error_content)
                        if isinstance(error_data, dict) and 'error' in error_data:
                            # JSON error format: {"error": "message"}
                            print(self.formatter.format_error(error_data['error']))
                        else:
                            # JSON but not error format - show as-is
                            print(self.formatter.format_error(error_content))
                    except (json.JSONDecodeError, ValueError):
                        # Not JSON - treat as text error
                        # Format: "error: message" or just "message"
                        if error_content.startswith('error:'):
                            print(self.formatter.format_error(error_content[6:].strip()))
                        else:
                            print(self.formatter.format_error(error_content))
                else:
                    # Just "error" with no details
                    print(self.formatter.format_error('Command failed'))
                return

            # Not an error - format normally
            formatted = self.formatter.format_command_output(result, display_mode=self.display_mode)

            if formatted:
                # Regular output - display as-is
                print(formatted)
        except Exception as exc:
            print(self.formatter.format_error(str(exc)))

    def _quit(self) -> None:
        """Exit the REPL"""
        self.running = False
        # Send bye command to server and wait for acknowledgment
        try:
            self.send_command('bye')
        except Exception:
            # Ignore errors during disconnect
            pass
        print(self.formatter.format_info('Goodbye!'))

    def _show_history(self) -> None:
        """Display command history"""
        history_len = readline.get_current_history_length()

        if history_len == 0:
            print(self.formatter.format_info('No commands in history'))
            return

        print(self.formatter.format_info(f'Command history ({history_len} entries):'))

        # Show last 20 commands
        start = max(1, history_len - 19)
        for i in range(start, history_len + 1):
            item = readline.get_history_item(i)
            if item:
                if self.formatter.use_color:
                    print(f'{Colors.DIM}{i:4d}{Colors.RESET}  {item}')
                else:
                    print(f'{i:4d}  {item}')


def cmdline_interactive(pipename: str, socketname: str, use_pipe_transport: bool, cmdarg) -> int:
    """
    Entry point for interactive CLI mode

    Args:
        pipename: Name of the named pipe
        socketname: Name of the Unix socket
        use_pipe_transport: If True, use pipe; otherwise use socket
        cmdarg: Command-line arguments

    Returns:
        Exit code (0 for success)
    """
    # Initialize connection variable for cleanup
    connection = None

    # Determine transport method
    if use_pipe_transport:
        # Use named pipe transport
        pipes = named_pipe(ROOT, pipename)
        if len(pipes) != 1:
            sys.stderr.write(f"Could not find ExaBGP's named pipe ({pipename})\n")
            sys.stderr.write('Available pipes:\n - ')
            sys.stderr.write('\n - '.join(pipes))
            sys.stderr.write('\n')
            sys.stderr.flush()
            return 1

        pipe_path = pipes[0]

        def send_command_pipe(command: str) -> str:
            """Send command via named pipe and return response"""
            try:
                # Expand shortcuts
                expanded = CommandShortcuts.expand_shortcuts(command)

                # Open pipe and send command
                with open(pipe_path, 'w') as writer:
                    writer.write(expanded + '\n')
                    writer.flush()

                # Read response (simplified - real implementation needs proper response handling)
                # For now, return acknowledgment
                return 'Command sent'
            except Exception as exc:
                return f'Error: {exc}'

        send_func = send_command_pipe
        daemon_uuid = None
    else:
        # Use Unix socket transport
        sockets = unix_socket(ROOT, socketname)
        if len(sockets) != 1:
            sys.stderr.write(f"Could not find ExaBGP's Unix socket ({socketname}.sock)\n")
            sys.stderr.write('Available sockets:\n - ')
            sys.stderr.write('\n - '.join(sockets))
            sys.stderr.write('\n')
            sys.stderr.flush()
            return 1

        socket_path = sockets[0]

        # Create persistent connection with health monitoring
        try:
            connection = PersistentSocketConnection(socket_path)
        except sock.error as exc:
            # Socket connection errors
            sys.stderr.write('\n')
            sys.stderr.write('╔════════════════════════════════════════════════════════╗\n')
            sys.stderr.write('║  ERROR: Could not connect to ExaBGP daemon             ║\n')
            sys.stderr.write('╠════════════════════════════════════════════════════════╣\n')
            sys.stderr.write(f'║  {str(exc):<54} ║\n')
            sys.stderr.write('╚════════════════════════════════════════════════════════╝\n')
            sys.stderr.write('\n')
            sys.stderr.flush()
            return 1
        except SystemExit:
            # Raised by _initial_ping() with user-friendly error already shown
            raise
        except Exception as exc:
            sys.stderr.write('\n')
            sys.stderr.write('╔════════════════════════════════════════════════════════╗\n')
            sys.stderr.write('║  ERROR: Unexpected error connecting to ExaBGP          ║\n')
            sys.stderr.write('╠════════════════════════════════════════════════════════╣\n')
            sys.stderr.write(f'║  {str(exc):<54} ║\n')
            sys.stderr.write('╚════════════════════════════════════════════════════════╝\n')
            sys.stderr.write('\n')
            sys.stderr.flush()
            return 1

        def send_command_persistent(command: str) -> str:
            """Send command via persistent connection"""
            expanded = CommandShortcuts.expand_shortcuts(command)
            return connection.send_command(expanded)

        send_func = send_command_persistent
        daemon_uuid = connection.daemon_uuid

    # Create and run interactive CLI
    try:
        cli = InteractiveCLI(send_func, daemon_uuid=daemon_uuid)
        cli.run()
        return 0
    except Exception as exc:
        sys.stderr.write(f'CLI error: {exc}\n')
        sys.stderr.flush()
        return 1
    finally:
        # Clean up persistent connection if it exists
        if connection is not None:
            try:
                connection.close()
            except (Exception, KeyboardInterrupt):
                # Ignore all errors during cleanup (including Ctrl+C)
                pass
