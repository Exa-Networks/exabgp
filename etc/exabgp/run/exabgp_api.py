#!/usr/bin/env python3
"""Shared library for ExaBGP API test scripts.

Provides buffered I/O for reliable communication with ExaBGP daemon.
Handles both text (v4) and JSON (v6) API response formats.

Usage:
    from exabgp_api import API

    api = API()
    api.send('announce route 10.0.0.0/24 next-hop 1.2.3.4')
    if not api.wait_for_ack():
        print('Command failed', file=sys.stderr)

    # Or send multiple commands and wait for all ACKs
    api.send('announce route 10.0.0.0/24 next-hop 1.2.3.4')
    api.send('announce route 10.0.1.0/24 next-hop 1.2.3.4')
    api.wait_for_ack(expected_count=2)

    # Wait for shutdown signal
    api.wait_for_shutdown()
"""

from __future__ import annotations

import json
import os
import select
import signal
import sys
import time
from typing import Any


class API:
    """ExaBGP API client with buffered I/O.

    Uses os.read() with internal buffering to properly handle responses
    that may arrive in chunks or be split across multiple reads.
    """

    def __init__(self, stdin: int | None = None, stdout: int | None = None):
        """Initialize API client.

        Args:
            stdin: File descriptor to read from (default: sys.stdin)
            stdout: File object to write to (default: sys.stdout)
        """
        self._stdin_fd = stdin if stdin is not None else sys.stdin.fileno()
        self._stdout = stdout if stdout is not None else sys.stdout
        self._buffer = ''

        # Install SIGPIPE handler
        signal.signal(signal.SIGPIPE, signal.SIG_DFL)

    def flush(self, msg: str) -> None:
        """Write message to stdout and flush.

        Args:
            msg: Message to send (should include newline if needed)
        """
        self._stdout.write(msg)
        self._stdout.flush()

    def send(self, command: str) -> None:
        """Send a command to ExaBGP.

        Args:
            command: Command string (newline added automatically)
        """
        self.flush(f'{command}\n')

    def read_line(self, timeout: float = 0.1) -> str | None:
        """Read a complete line from stdin using buffered I/O.

        Reads data into internal buffer and returns complete lines.
        Handles data that arrives in chunks across multiple reads.

        Args:
            timeout: Seconds to wait for data (default: 0.1)

        Returns:
            Complete line (without newline) or None if no complete line available
        """
        # Check if we already have a complete line in buffer
        if '\n' in self._buffer:
            line, self._buffer = self._buffer.split('\n', 1)
            return line

        # Read more data if available
        try:
            ready, _, _ = select.select([self._stdin_fd], [], [], timeout)
            if ready:
                chunk = os.read(self._stdin_fd, 4096).decode('utf-8', errors='replace')
                if chunk:
                    self._buffer += chunk
        except (OSError, IOError):
            return None

        # Check again for complete line
        if '\n' in self._buffer:
            line, self._buffer = self._buffer.split('\n', 1)
            return line

        return None

    def parse_answer(self, line: str) -> str | None:
        """Parse answer type from response line.

        Handles both text and JSON formats:
        - Text: "done", "error", "shutdown"
        - JSON: {"answer": "done|error|shutdown", ...}

        Args:
            line: Response line to parse

        Returns:
            Answer type ('done', 'error', 'shutdown') or None if not an answer
        """
        if not line:
            return None

        if line.startswith('{'):
            # JSON format
            try:
                data = json.loads(line)
                return data.get('answer')
            except (json.JSONDecodeError, TypeError):
                return None
        else:
            # Text format - check if it's a known answer
            if line in ('done', 'error', 'shutdown'):
                return line
            return None

    def wait_for_ack(self, expected_count: int = 1, timeout: float = 2.0) -> bool:
        """Wait for ACK responses from ExaBGP.

        Polls stdin until all expected ACK messages are received.
        Uses buffered I/O to handle responses arriving in chunks.

        Args:
            expected_count: Number of ACK messages expected (default: 1)
            timeout: Total timeout in seconds (default: 2.0)

        Returns:
            True if all ACKs received successfully
            False if any command failed or timeout occurred

        Raises:
            SystemExit: If ExaBGP sends shutdown message
        """
        received = 0
        start_time = time.time()

        while received < expected_count:
            # Check timeout
            elapsed = time.time() - start_time
            if elapsed >= timeout:
                return False

            # Read a line (uses internal buffer)
            line = self.read_line(0.1)
            if line is None:
                continue

            # Parse the answer
            answer = self.parse_answer(line)
            if answer == 'done':
                received += 1
            elif answer == 'error':
                return False
            elif answer == 'shutdown':
                raise SystemExit(0)
            # Ignore other messages (could be BGP updates, data responses, etc.)

        return True

    def read_response(self, timeout: float = 2.0) -> dict | str | None:
        """Read and parse a complete response from ExaBGP.

        Collects lines until we get an 'answer' terminator (done/error/shutdown).
        Returns accumulated data along with the answer.

        Args:
            timeout: Maximum time to wait for response

        Returns:
            dict: {'data': [...], 'answer': 'done|error'} if data received
            dict: {'answer': 'done|error'} if only terminator received
            str: Raw text if non-JSON response
            None: Timeout with no data received

        Raises:
            SystemExit: If ExaBGP sends shutdown message
        """
        start_time = time.time()
        responses: list[Any] = []

        while True:
            # Check timeout
            elapsed = time.time() - start_time
            if elapsed >= timeout:
                break

            # Read a line
            line = self.read_line(0.1)
            if line is None:
                continue

            # Try to parse as JSON
            try:
                data = json.loads(line)
                # Check for terminator
                if isinstance(data, dict):
                    answer = data.get('answer')
                    if answer in ('done', 'error', 'shutdown'):
                        if answer == 'shutdown':
                            raise SystemExit(0)
                        if responses:
                            return {'data': responses, 'answer': answer}
                        return data
                # Accumulate non-terminator responses
                responses.append(data)
            except json.JSONDecodeError:
                # Not JSON - check for text terminators
                if line in ('done', 'error', 'shutdown'):
                    if line == 'shutdown':
                        raise SystemExit(0)
                    if responses:
                        return {'data': responses, 'answer': line}
                    return {'answer': line}
                # Return raw text
                return line

        # Timeout - return accumulated responses or None
        if responses:
            return {'data': responses, 'answer': 'timeout'}
        return None

    def send_and_wait(self, command: str, timeout: float = 2.0) -> bool:
        """Send command and wait for ACK.

        Convenience method combining send() and wait_for_ack().

        Args:
            command: Command to send
            timeout: Timeout for ACK

        Returns:
            True if command succeeded (got 'done')
            False if command failed or timed out
        """
        self.send(command)
        return self.wait_for_ack(expected_count=1, timeout=timeout)

    def wait_for_shutdown(self, timeout: float = 5.0) -> None:
        """Wait for shutdown signal from ExaBGP.

        Blocks until shutdown is received, parent dies, or timeout expires.

        Args:
            timeout: Maximum time to wait (default: 5.0 seconds)
        """
        start_time = time.time()
        try:
            while os.getppid() != 1 and time.time() - start_time < timeout:
                line = self.read_line(0.5)
                if line is not None:
                    answer = self.parse_answer(line)
                    if answer == 'shutdown' or 'shutdown' in line:
                        break
        except (IOError, OSError):
            pass


# Convenience functions for simple scripts that don't need the class

_api: API | None = None


def _get_api() -> API:
    """Get or create singleton API instance."""
    global _api
    if _api is None:
        _api = API()
    return _api


def flush(msg: str) -> None:
    """Write message to stdout and flush."""
    _get_api().flush(msg)


def send(command: str) -> None:
    """Send command to ExaBGP."""
    _get_api().send(command)


def wait_for_ack(expected_count: int = 1, timeout: float = 2.0) -> bool:
    """Wait for ACK responses from ExaBGP."""
    return _get_api().wait_for_ack(expected_count, timeout)


def read_response(timeout: float = 2.0) -> dict | str | None:
    """Read complete response from ExaBGP."""
    return _get_api().read_response(timeout)


def send_and_wait(command: str, timeout: float = 2.0) -> bool:
    """Send command and wait for ACK."""
    return _get_api().send_and_wait(command, timeout)


def wait_for_shutdown(timeout: float = 5.0) -> None:
    """Wait for shutdown signal."""
    _get_api().wait_for_shutdown(timeout)
