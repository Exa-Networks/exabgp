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

# an announce block nests family, then next-hop, then routes, while a withdraw
# block nests family then routes, so the walker below is bounded rather than
# assuming either shape
MAX_EVENT_DEPTH = 8
MAX_EVENT_NLRI = 4096


def nlris_of(block: Any) -> list[str]:
    """Every NLRI inside an announce or withdraw block, as a string.

    A route is identified by its nlri when it has one and by the hex of its
    wire encoding otherwise, which is what the families rendering their own
    fields, such as mcast-vpn, give instead.
    """
    found: list[str] = []
    stack: list[tuple[Any, int]] = [(block, 0)]

    while stack and len(found) < MAX_EVENT_NLRI:
        node, depth = stack.pop()
        if depth > MAX_EVENT_DEPTH:
            continue
        if isinstance(node, dict):
            if 'eor' in node:
                found.append('eor')
                continue
            name = node.get('nlri') or node.get('raw')
            if isinstance(name, str):
                found.append(name)
                continue
            for value in node.values():
                stack.append((value, depth + 1))
        elif isinstance(node, list):
            for value in node:
                stack.append((value, depth + 1))
        elif isinstance(node, str):
            found.append(node)

    return found


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
        self._sent_announce: dict[str, int] = {}
        self._sent_withdraw: dict[str, int] = {}
        self._states: dict[str, int] = {}

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
            self._record(line)
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
            self._record(line)
            return line

        return None

    def _record(self, line: str) -> None:
        """Count an event ExaBGP reported, so a script can wait on one.

        An ACK only says a command was parsed and queued. A command sent
        on the strength of an ACK alone can still overtake an earlier
        announce inside the RIB, so the scripts which care about ordering
        wait on the event itself.
        """
        if not line.startswith('{'):
            return

        try:
            event = json.loads(line)
        except (json.JSONDecodeError, TypeError):
            return

        if not isinstance(event, dict):
            return

        neighbor = event.get('neighbor')
        if not isinstance(neighbor, dict):
            return

        kind = event.get('type')

        if kind in ('state', 'fsm'):
            state = neighbor.get('state')
            if isinstance(state, str):
                self._states[state] = self._states.get(state, 0) + 1
            return

        # only what we put on the wire, never what the peer sent us
        if kind != 'update' or neighbor.get('direction') != 'send':
            return

        message = neighbor.get('message')
        if not isinstance(message, dict):
            return
        update = message.get('update')
        if not isinstance(update, dict):
            return

        for action, counter in (('announce', self._sent_announce), ('withdraw', self._sent_withdraw)):
            families = update.get(action, {})
            if not isinstance(families, dict):
                continue
            for family, routes in families.items():
                for nlri in nlris_of(routes):
                    counter[nlri] = counter.get(nlri, 0) + 1
                    # a barrier may name the family instead, for the families
                    # whose routes have no single string which identifies them
                    counter[family] = counter.get(family, 0) + 1

    @staticmethod
    def _reached(wanted: tuple, seen: dict[str, int]) -> bool:
        return all(seen.get(key, 0) >= count for key, count in wanted)

    def trace(self, note: str) -> None:
        """Append a note to the file named by EXABGP_API_TRACE, if any.

        A run script talks to ExaBGP over its stdout, so it cannot print
        anywhere a human will see. Without this a barrier which never opens
        looks the same from outside as a script which finished.
        """
        where = os.environ.get('EXABGP_API_TRACE')
        if not where:
            return
        try:
            with open(where, 'a') as handle:
                handle.write(f'{os.getpid()} {note}\n')
        except OSError:
            pass

    def counters(self) -> dict[str, dict[str, int]]:
        """What has been seen so far, for a failure message worth reading."""
        return {
            'announce': dict(self._sent_announce),
            'withdraw': dict(self._sent_withdraw),
            'state': dict(self._states),
        }

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

    def wait_for_ack(
        self,
        expected_count: int = 1,
        timeout: float = 2.0,
        announce: tuple = (),
        withdraw: tuple = (),
        state: tuple = (),
    ) -> bool:
        """Wait for ACK responses from ExaBGP, and for the events asked for.

        Polls stdin until all expected ACK messages are received.
        Uses buffered I/O to handle responses arriving in chunks.

        An ACK says a command was parsed and queued, nothing more. Pass
        announce, withdraw or state to wait on what actually happened, which
        is what a script needs before sending a command whose effect depends
        on the previous one having left. Counts are cumulative over the life
        of the script, not per call.

        Args:
            expected_count: Number of ACK messages expected (default: 1)
            timeout: Total timeout in seconds (default: 2.0)
            announce: ((nlri, count), ...) sent announcements to wait for
            withdraw: ((nlri, count), ...) sent withdrawals to wait for
            state: ((name, count), ...) neighbour states to wait for, where a
                name is up, down, connected or an FSM state such as ESTABLISHED

        Returns:
            True if all ACKs and every requested event arrived
            False if any command failed or timeout occurred

        Raises:
            SystemExit: If ExaBGP sends shutdown message
        """
        received = 0
        start_time = time.time()

        while (
            received < expected_count
            or not self._reached(announce, self._sent_announce)
            or not self._reached(withdraw, self._sent_withdraw)
            or not self._reached(state, self._states)
        ):
            # Check timeout
            elapsed = time.time() - start_time
            if elapsed >= timeout:
                self.trace(
                    f'gave up after {timeout}s wanting acks={expected_count} '
                    f'announce={announce} withdraw={withdraw} state={state} saw {self.counters()}'
                )
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

        A script has to stay alive until ExaBGP is done with it: one which
        returns early is respawned, and the respawned one waits on events which
        have already gone by.

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


def wait_for_ack(
    expected_count: int = 1,
    timeout: float = 2.0,
    announce: tuple = (),
    withdraw: tuple = (),
    state: tuple = (),
) -> bool:
    """Wait for ACK responses from ExaBGP, and for the events asked for."""
    return _get_api().wait_for_ack(expected_count, timeout, announce, withdraw, state)


def counters() -> dict[str, dict[str, int]]:
    """What has been seen so far, for a failure message worth reading."""
    return _get_api().counters()


def trace(note: str) -> None:
    """Append a note to the file named by EXABGP_API_TRACE, if any."""
    _get_api().trace(note)


def read_response(timeout: float = 2.0) -> dict | str | None:
    """Read complete response from ExaBGP."""
    return _get_api().read_response(timeout)


def send_and_wait(command: str, timeout: float = 2.0) -> bool:
    """Send command and wait for ACK."""
    return _get_api().send_and_wait(command, timeout)


def wait_for_shutdown(timeout: float = 5.0) -> None:
    """Wait for shutdown signal."""
    _get_api().wait_for_shutdown(timeout)
