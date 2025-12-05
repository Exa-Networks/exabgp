"""persistent_connection.py

Persistent Unix socket connection with background health monitoring for CLI.

Created by Thomas Mangin on 2010-01-15.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import json
import os
import signal
import socket as sock
import sys
import threading
import time
from queue import Queue, Empty

from exabgp.cli.colors import Colors


class PersistentSocketConnection:
    """Persistent Unix socket connection with background health monitoring

    Implements fixes for multi-client connection issues:
    - Fix 1: Request ID tracking for response correlation
    - Fix 3: Command retry on reconnect
    """

    def __init__(self, socket_path: str) -> None:
        self.socket_path = socket_path
        self.socket: sock.socket | None = None
        self.daemon_uuid: str | None = None
        self.last_ping_time: float = 0
        self.consecutive_failures: int = 0
        self.max_failures: int = 3
        self.health_interval: int = 10  # seconds
        self.running: bool = True
        self.reconnecting: bool = False
        self.command_in_progress: bool = False  # Track if user command is being executed
        self.pending_user_command: bool = False  # Track if waiting for user command response
        self.lock = threading.Lock()

        # Client identity for connection tracking
        import uuid as uuid_lib

        self.client_uuid = str(uuid_lib.uuid4())
        self.client_start_time = time.time()

        # Fix 1: Request ID counter for correlating commands with responses
        self._request_id_counter: int = 0
        self._current_request_id: str | None = None

        # Fix 3: Store last command for retry on reconnect
        self._last_command: str | None = None
        self._command_needs_retry: bool = False

        # Response handling
        self.pending_responses: Queue[str] = Queue()
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

    def _generate_request_id(self) -> str:
        """Generate unique request ID for command tracking (Fix 1)."""
        with self.lock:
            self._request_id_counter += 1
            return f'{self.client_uuid[:8]}-{self._request_id_counter}'

    def _connect(self) -> None:
        """Establish socket connection"""
        self.socket = sock.socket(sock.AF_UNIX, sock.SOCK_STREAM)
        full_path = self.socket_path if self.socket_path.endswith('.sock') else self.socket_path + 'exabgp.sock'
        self.socket.connect(full_path)
        self.socket.settimeout(0.5)  # Initial timeout for sync ping

    def _initial_ping(self) -> None:
        """Send initial synchronous ping to get daemon UUID before starting background threads"""
        try:
            # Send ping (v6 API format)
            ping_cmd = f'session ping {self.client_uuid} {self.client_start_time}\n'
            try:
                self.socket.sendall(ping_cmd.encode('utf-8'))  # type: ignore[union-attr]
            except (BrokenPipeError, ConnectionResetError):
                # Connection rejected before we could send
                sys.stderr.write('\n')
                sys.stderr.write('╔════════════════════════════════════════════════════════╗\n')
                sys.stderr.write('║  ERROR: Connection rejected by daemon                  ║\n')
                sys.stderr.write('╠════════════════════════════════════════════════════════╣\n')
                sys.stderr.write('║  The ExaBGP daemon closed the connection.              ║\n')
                sys.stderr.write('║  Please check if ExaBGP is running properly.           ║\n')
                sys.stderr.write('╚════════════════════════════════════════════════════════╝\n')
                sys.stderr.write('\n')
                sys.stderr.flush()
                sys.exit(1)

            # Read response synchronously
            response_buffer = ''
            while True:
                data = self.socket.recv(4096)  # type: ignore[union-attr]
                if not data:
                    # Connection closed by daemon
                    sys.stderr.write('\n')
                    sys.stderr.write('╔════════════════════════════════════════════════════════╗\n')
                    sys.stderr.write('║  ERROR: Connection closed by daemon                    ║\n')
                    sys.stderr.write('╠════════════════════════════════════════════════════════╣\n')
                    sys.stderr.write('║  The ExaBGP daemon closed the connection unexpectedly. ║\n')
                    sys.stderr.write('║  Please check if ExaBGP is running properly.           ║\n')
                    sys.stderr.write('╚════════════════════════════════════════════════════════╝\n')
                    sys.stderr.write('\n')
                    sys.stderr.flush()
                    sys.exit(1)

                response_buffer += data.decode('utf-8')

                # Check if we have complete response (pong + done OR error + done)
                if '\ndone\n' in response_buffer or response_buffer.endswith('done\n'):
                    break

            # Check for immediate rejection (error response from daemon)
            if response_buffer.startswith('error:'):
                # Extract and display the error message from daemon
                error_msg = response_buffer.split('\n')[0]
                if error_msg.startswith('error:'):
                    error_msg = error_msg[6:].strip()
                sys.stderr.write('\n')
                sys.stderr.write('╔════════════════════════════════════════════════════════╗\n')
                sys.stderr.write('║  ERROR: Connection rejected by daemon                  ║\n')
                sys.stderr.write('╠════════════════════════════════════════════════════════╣\n')
                sys.stderr.write(f'║  {error_msg:<54} ║\n')
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
                    # Connection established but marked as not active
                    sys.stderr.write('\n')
                    sys.stderr.write('╔════════════════════════════════════════════════════════╗\n')
                    sys.stderr.write('║  ERROR: Connection not active                          ║\n')
                    sys.stderr.write('╠════════════════════════════════════════════════════════╣\n')
                    sys.stderr.write('║  The daemon rejected this CLI session.                 ║\n')
                    sys.stderr.write('║  Please check daemon logs for details.                 ║\n')
                    sys.stderr.write('╚════════════════════════════════════════════════════════╝\n')
                    sys.stderr.write('\n')
                    sys.stderr.flush()
                    sys.exit(1)

                # Print connection message BEFORE returning (so it appears before banner)
                sys.stderr.write(f'✓ Connected to ExaBGP daemon (UUID: {self.daemon_uuid})\n')
                sys.stderr.flush()

            # Switch to non-blocking for background threads
            self.socket.settimeout(0.1)  # type: ignore[union-attr]

        except sock.timeout:
            sys.stderr.write('\n')
            sys.stderr.write('╔════════════════════════════════════════════════════════╗\n')
            sys.stderr.write('║  ERROR: Connection timeout                             ║\n')
            sys.stderr.write('╠════════════════════════════════════════════════════════╣\n')
            sys.stderr.write('║  ExaBGP daemon is not responding to commands.          ║\n')
            sys.stderr.write('║                                                        ║\n')
            sys.stderr.write('║  Possible causes:                                      ║\n')
            sys.stderr.write('║    • The daemon is busy or overloaded                  ║\n')
            sys.stderr.write('║    • The daemon crashed after accepting connection     ║\n')
            sys.stderr.write('║                                                        ║\n')
            sys.stderr.write('║  Please check if ExaBGP is running properly.           ║\n')
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

        def signal_handler(signum: int, frame: object) -> None:
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
        except OSError:
            pass

    def _reconnect(self, max_attempts: int = 3, retry_delay: int = 2) -> bool:
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
            except OSError:
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

                # Fix 3: Check if there's a command that needs retry
                with self.lock:
                    needs_retry = self._command_needs_retry
                    last_cmd = self._last_command
                    # Clear retry flag to prevent duplicate retries
                    self._command_needs_retry = False

                if needs_retry and last_cmd:
                    sys.stderr.write(f'⟳ Retrying command: {last_cmd[:50]}...\n')
                    sys.stderr.flush()
                    # Queue the retry response for the waiting send_command
                    retry_response = self.send_command(last_cmd, is_retry=True)
                    # The retry response will be handled by the main thread
                    self.pending_responses.put(retry_response)

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

    def _read_loop(self) -> None:
        """Background thread: continuously read from socket"""
        while self.running:
            try:
                data = self.socket.recv(4096)  # type: ignore[union-attr]
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

    def _health_monitor(self) -> None:
        """Background thread: send periodic pings"""
        # Initial sync ping already done in __init__, start periodic monitoring
        while self.running:
            # Skip health checks if reconnecting
            if not self.reconnecting:
                current_time = time.time()
                if current_time - self.last_ping_time >= self.health_interval:
                    self._send_ping()

            time.sleep(1)  # Check every second

    def _send_ping(self) -> None:
        """Send ping command (internal, not user-initiated)"""
        # Skip if reconnecting or no socket
        if self.reconnecting or not self.socket:
            return

        with self.lock:
            # Skip ping if a user command is in progress or pending
            if self.command_in_progress or self.pending_user_command:
                return

            try:
                # Include client UUID and start time to track active connection (v6 API format)
                ping_cmd = f'session ping {self.client_uuid} {self.client_start_time}\n'
                self.socket.sendall(ping_cmd.encode('utf-8'))
                self.last_ping_time = time.time()
            except OSError:
                # Socket error - read loop will handle reconnection
                # Don't print error or exit here
                pass

    def _handle_ping_response(self, response: str) -> None:
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

    def send_command(self, command: str, is_retry: bool = False) -> str:
        """Send user command and wait for response.

        Fix 3: Commands can be retried after reconnection if they were in-flight.
        """
        # Mark command in progress to prevent ping interference
        with self.lock:
            self.command_in_progress = True
            self.pending_user_command = True
            # Fix 3: Store command for potential retry (but not if this IS a retry)
            if not is_retry:
                self._last_command = command
                self._command_needs_retry = True

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
                    if self.socket is not None:
                        self.socket.sendall((command + '\n').encode('utf-8'))
                    else:
                        return 'Error: Not connected'
            except OSError as exc:
                return f'Error: {exc}'

            # Wait for response (with timeout)
            try:
                response: str = self.pending_responses.get(timeout=5.0)
                # Fix 3: Command completed successfully, no retry needed
                with self.lock:
                    self._command_needs_retry = False
                return response
            except Empty:
                return 'Error: Timeout waiting for response'
        finally:
            # Always clear the flags when done (even on error/timeout)
            with self.lock:
                self.command_in_progress = False
                self.pending_user_command = False

    def close(self) -> None:
        """Close connection and stop threads"""
        try:
            self.running = False

            # Close socket (triggers read thread to exit)
            if self.socket:
                try:
                    # Shutdown socket first (stops I/O operations)
                    self.socket.shutdown(sock.SHUT_RDWR)
                except OSError:
                    pass

                try:
                    # Then close the socket
                    self.socket.close()
                except OSError:
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
