"""process.py

Created by Thomas Mangin on 2011-05-02.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import os
import errno
import time
import subprocess
import select
import fcntl
import asyncio
import collections

from typing import Any, Callable, Dict, Generator, IO, List, Tuple, TypeVar, cast, TYPE_CHECKING
from threading import Thread

if TYPE_CHECKING:
    from exabgp.bgp.neighbor import Neighbor
    from exabgp.reactor.peer import Peer
    from exabgp.bgp.message import Open, Update, Notify
    from exabgp.bgp.fsm import FSM

from exabgp.util.errstr import errstr
from exabgp.reactor.network.error import error

from exabgp.configuration.core.format import formated
from exabgp.reactor.api.response import Response
from exabgp.reactor.api.response.answer import Answer

from exabgp.bgp.message import Message
from exabgp.bgp.message.open.capability import Negotiated
from exabgp.logger import log, lazymsg

from exabgp.version import json as json_version
from exabgp.version import text as text_version

from exabgp.environment import getenv

# TypeVar for silenced decorator - preserves function signature
_F = TypeVar('_F', bound=Callable[..., None])


# pylint: disable=no-self-argument,not-callable,unused-argument,invalid-name


class ProcessError(Exception):
    """Base exception for process-related errors."""

    pass


class ProcessStartError(ProcessError):
    """Failed to start subprocess."""

    pass


class ProcessCommunicationError(ProcessError):
    """Failed to communicate with subprocess."""

    pass


class ProcessWriteError(ProcessCommunicationError):
    """Failed to write to process stdin (broken pipe)."""

    pass


class ProcessReadError(ProcessCommunicationError):
    """Failed to read from process stdout."""

    pass


class ProcessRespawnError(ProcessError):
    """Process respawned too many times."""

    pass


def preexec_helper() -> None:
    # make this process a new process group
    # os.setsid()
    # This prevent the signal to be sent to the children (and create a new process group)
    os.setpgrp()
    # signal.signal(signal.SIGINT, signal.SIG_IGN)


class Processes:
    # how many time can a process can respawn in the time interval
    respawn_timemask: int = 0xFFFFFF - 0b111111
    # '0b111111111111111111000000' (around a minute, 63 seconds)

    _dispatch: Dict[int, Any] = {}

    def __init__(self) -> None:
        self.clean()
        self.silence: bool = False
        self._buffer: Dict[str, str] = {}
        self._configuration: Dict[str, Dict[str, Any]] = {}
        self._restart: Dict[str, bool] = {}

        self.respawn_number: int = 5 if getenv().api.respawn else 0
        self.terminate_on_error: bool = getenv().api.terminate
        self._default_ack: bool = getenv().api.ack

        # Async mode support
        self._async_mode: bool = False
        self._loop: asyncio.AbstractEventLoop | None = None
        # Write queue for async mode (process_name -> deque of strings to write)
        self._write_queue: Dict[str, collections.deque] = {}
        self._command_queue: collections.deque[Tuple[str, str]] = collections.deque()

    def number(self) -> int:
        return len(self._process)

    def clean(self) -> None:
        self.fds: List[int] = []
        self._process: Dict[str, subprocess.Popen[bytes]] = {}
        self._encoder: Dict[str, Response.JSON | Response.Text] = {}
        self._ackjson: Dict[str, bool] = {}
        self._ack: Dict[str, bool] = {}
        self._sync: Dict[str, bool] = {}  # Per-service sync mode (default: False)
        self._broken: List[str] = []
        self._respawning: Dict[str, Dict[int, int]] = {}

    def _handle_problem(self, process: str) -> None:
        if process not in self._process:
            return
        if self.respawn_number and self._restart[process]:
            log.debug(lazymsg('process.ended.restarting process={p}', p=process), 'processes')
            self._terminate(process)
            self._start(process)
        else:
            log.debug(lazymsg('process.ended process={p}', p=process), 'processes')
            self._terminate(process)

    def _terminate(self, process_name: str) -> Thread:
        log.debug(lazymsg('process.terminating process={p}', p=process_name), 'processes')
        process = self._process[process_name]

        # Remove async reader if in async mode
        if self._async_mode and self._loop and process.stdout:
            try:
                fd = process.stdout.fileno()
                self._loop.remove_reader(fd)
                log.debug(lazymsg('async.reader.removed process={p} fd={fd}', p=process_name, fd=fd), 'processes')
            except (ValueError, OSError):
                pass  # Reader might not be registered or FD already closed

        del self._process[process_name]
        self._update_fds()
        thread = Thread(target=self._terminate_run, args=(process, process_name))
        thread.start()
        return thread

    def _terminate_run(self, process: subprocess.Popen[bytes], process_name: str) -> None:
        try:
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                log.debug(lazymsg('process.kill.forced process={p}', p=process_name), 'processes')
                process.kill()
                process.wait(timeout=1)
        except (OSError, KeyError, subprocess.TimeoutExpired):
            # the process is most likely already dead
            pass

    def terminate(self) -> None:
        for process in list(self._process):
            if not self.silence:
                try:
                    self.write(process, self._encoder[process].shutdown())
                except ProcessError:
                    pass
        self.silence = True
        # waiting a little to make sure IO is flushed to the pipes
        # we are using unbuffered IO but still ..
        time.sleep(0.1)
        for process in list(self._process):
            try:
                t = self._terminate(process)
                t.join()
            except OSError:
                # we most likely received a SIGTERM signal and our child is already dead
                log.debug(lazymsg('child process {p} was already dead', p=process), 'processes')
        self.clean()

    async def terminate_async(self) -> None:
        """Async version of terminate() - sends shutdown signal and waits for processes

        Critical: Must flush write queue after sending shutdown signal to ensure
        API processes receive it before termination.
        """
        for process in list(self._process):
            if not self.silence:
                try:
                    self.write(process, self._encoder[process].shutdown())
                except ProcessError:
                    pass
        # Flush all queued shutdown messages
        await self.flush_write_queue_async()
        self.silence = True
        # waiting a little to make sure IO is flushed to the pipes
        await asyncio.sleep(0.1)
        for process in list(self._process):
            try:
                t = self._terminate(process)
                t.join()
            except OSError:
                # we most likely received a SIGTERM signal and our child is already dead
                log.debug(lazymsg('child process {p} was already dead', p=process), 'processes')
        self.clean()

    def _start(self, process: str) -> None:
        if not self._restart.get(process, True):
            return

        try:
            if process in self._process:
                log.debug(lazymsg('process.start.skipped process={p} reason=already_running', p=process), 'processes')
                return

            if process not in self._configuration:
                log.debug(lazymsg('process.start.skipped process={p} reason=no_configuration', p=process), 'processes')
                return
            # Prevent some weird termcap data to be created at the start of the PIPE
            # \x1b[?1034h (no-eol) (esc)
            os.environ['TERM'] = 'dumb'

            configuration = self._configuration[process]

            run = configuration.get('run', '')
            if run:
                use_json = configuration.get('encoder', 'text') == 'json'
                self._encoder[process] = Response.JSON(json_version) if use_json else Response.Text(text_version)
                # TODO: Future enhancement - add 'ack-format' config option for JSON ACKs
                # Would allow: ack-format json; to send {"status": "ok"} instead of "done"
                self._ackjson[process] = False
                # Initialize per-process ACK state (process config overrides global default)
                self._ack[process] = configuration.get('ack', self._default_ack)

                # Prepare environment variables for child process
                child_env = os.environ.copy()
                if 'env' in configuration:
                    child_env.update(configuration['env'])

                self._process[process] = subprocess.Popen(
                    run,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    env=child_env,
                    preexec_fn=preexec_helper,
                    # This flags exists for python 2.7.3 in the documentation but on on my MAC
                    # creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
                )
                self._update_fds()
                # Make stdout non-blocking for reading
                fcntl.fcntl(self._get_stdout(process).fileno(), fcntl.F_SETFL, os.O_NONBLOCK)
                # Make stdin non-blocking for writing (prevents blocking asyncio event loop)
                fcntl.fcntl(self._get_stdin(process).fileno(), fcntl.F_SETFL, os.O_NONBLOCK)

                # Register async reader if in async mode
                if self._async_mode and self._loop:
                    fd = self._get_stdout(process).fileno()
                    self._loop.add_reader(fd, self._async_reader_callback, process)
                    log.debug(lazymsg('async.reader.registered process={p} fd={fd}', p=process, fd=fd), 'processes')

                log.debug(lazymsg('process.forked process={p}', p=process), 'processes')

                self._restart[process] = self._configuration[process]['respawn']
                around_now = int(time.time()) & self.respawn_timemask
                if process in self._respawning:
                    if around_now in self._respawning[process]:
                        self._respawning[process][around_now] += 1
                        # we are respawning too fast
                        if self._respawning[process][around_now] > self.respawn_number:
                            log.critical(
                                lazymsg(
                                    'process.respawn.exceeded process={p} limit={limit}',
                                    p=process,
                                    limit=self.respawn_number,
                                ),
                                'processes',
                            )
                            raise ProcessError
                    else:
                        # reset long time since last respawn
                        self._respawning[process] = {around_now: 1}
                else:
                    # record respawing
                    self._respawning[process] = {around_now: 1}

        except (subprocess.CalledProcessError, OSError, ValueError) as exc:
            self._broken.append(process)
            log.debug(lazymsg('could not start process {p}', p=process), 'processes')
            log.debug(lazymsg('reason: {e}', e=exc), 'processes')

    def start(self, configuration: Dict[str, Dict[str, Any]], restart: bool = False) -> None:
        # Terminate processes that are no longer in configuration
        for process in list(self._process):
            if process not in configuration:
                self._terminate(process)

        # Identify which processes need restart (compare before updating self._configuration)
        processes_to_restart = set()
        if restart:
            for process in configuration:
                if process in self._process:
                    if self._configuration.get(process, {}) != configuration[process]:
                        log.debug(lazymsg('process.config.changed process={p} action=restart', p=process), 'processes')
                        processes_to_restart.add(process)
                    else:
                        log.debug(lazymsg('process.config.unchanged process={p} action=keep', p=process), 'processes')

        # Update configuration (needed by _start())
        self._configuration = configuration

        # Start/restart processes
        for process in configuration:
            if process in list(self._process):
                if process in processes_to_restart:
                    self._terminate(process)
                    self._start(process)
                continue
            self._start(process)

    def broken(self, neighbor: 'Neighbor') -> bool:
        if self._broken:
            for process in self._configuration:
                if process in self._broken:
                    return True
        return False

    def _get_stdout(self, process: str) -> IO[bytes]:
        """Get stdout for a process, asserting it exists.

        Safe to call because all processes are created with stdout=PIPE in _start().
        """
        stdout = self._process[process].stdout
        assert stdout is not None, f'Process {process} has no stdout (should be impossible)'
        return stdout

    def _get_stdin(self, process: str) -> IO[bytes]:
        """Get stdin for a process, asserting it exists.

        Safe to call because all processes are created with stdin=PIPE in _start().
        """
        stdin = self._process[process].stdin
        assert stdin is not None, f'Process {process} has no stdin (should be impossible)'
        return stdin

    def _update_fds(self) -> None:
        self.fds = [self._get_stdout(process).fileno() for process in self._process]

    def received(self) -> Generator[Tuple[str, str], None, None]:
        consumed_data = False

        for process in list(self._process):
            try:
                proc = self._process[process]
                poll = proc.poll()

                poller = select.poll()
                stdout = self._get_stdout(process)
                poller.register(
                    stdout,
                    select.POLLIN | select.POLLPRI | select.POLLHUP | select.POLLNVAL | select.POLLERR,
                )

                ready = False
                for _, event in poller.poll(0):
                    if event & select.POLLIN or event & select.POLLPRI:
                        ready = True
                    elif event & select.POLLHUP or event & select.POLLERR or event & select.POLLNVAL:
                        self._handle_problem(process)

                if not ready:
                    continue

                try:
                    # Calling next() on Linux and OSX works perfectly well
                    # but not on OpenBSD where it always raise StopIteration
                    # and only read() works (not even readline)
                    buf = str(stdout.read(16384), 'ascii')
                    if buf == '' and poll is not None:
                        # if proc.poll() is None then
                        # process is fine, we received an empty line because
                        # we're doing .read() on a non-blocking pipe and
                        # the process maybe has nothing to send yet
                        self._handle_problem(process)
                        continue

                    raw = self._buffer.get(process, '') + buf

                    while '\n' in raw:
                        line, raw = raw.split('\n', 1)
                        line = line.rstrip()
                        consumed_data = True
                        if line.startswith('debug '):
                            log.warning(
                                lazymsg('api.debug.received process={pr} info={info}', pr=process, info=line[6:]), 'api'
                            )
                        else:
                            log.debug(
                                lazymsg('api.command.received process={pr} command={ln}', pr=process, ln=line),
                                'processes',
                            )
                            yield (process, formated(line))

                    self._buffer[process] = raw

                except OSError as exc:
                    if not exc.errno or exc.errno in error.fatal:
                        # if the program exits we can get an IOError with errno code zero !
                        self._handle_problem(process)
                    elif exc.errno in error.block:
                        # we often see errno.EINTR: call interrupted and
                        # we most likely have data, we will try to read them a the next loop iteration
                        pass
                    else:
                        log.debug(
                            lazymsg('process.error.unexpected errno={errstr}', errstr=errstr(exc)),
                            'processes',
                        )
                    continue
                except StopIteration:
                    if not consumed_data:
                        self._handle_problem(process)
                    continue

                # proc.poll returns None if the process is still fine
                # -[signal], like -15, if the process was terminated
                if poll is not None:
                    self._handle_problem(process)
                    return

            except KeyError:
                pass
            except (subprocess.CalledProcessError, OSError, ValueError):
                self._handle_problem(process)

    def setup_async_readers(self, loop: asyncio.AbstractEventLoop) -> None:
        """Setup async readers for API process stdout using loop.add_reader()

        This integrates API process communication with the asyncio event loop.
        Instead of using select.poll() (which doesn't work with asyncio), we
        register callbacks that are invoked when data is available.

        Args:
            loop: The asyncio event loop to register readers with
        """
        self._async_mode = True
        self._loop = loop

        # Register reader for each existing process
        for process_name in self._process:
            proc = self._process[process_name]
            if proc.stdout:
                fd = proc.stdout.fileno()
                # Register callback to be called when stdout has data available
                loop.add_reader(fd, self._async_reader_callback, process_name)
                log.debug(lazymsg('async.reader.registered process={p} fd={fd}', p=process_name, fd=fd), 'processes')

    def _async_reader_callback(self, process_name: str) -> None:
        """Callback invoked by event loop when API process stdout has data

        This is called automatically by asyncio when data is available.
        It reads the data, buffers incomplete lines, and queues complete
        commands for processing.

        Args:
            process_name: Name of the process with available data
        """
        if process_name not in self._process:
            # Process already removed - shouldn't happen but be defensive
            # Try to remove reader anyway in case of race condition
            try:
                if self._async_mode and self._loop:
                    # We don't have the FD anymore, but asyncio will handle cleanup
                    pass
            except (ValueError, OSError):
                pass
            return

        try:
            proc = self._process[process_name]
            poll = proc.poll()

            # Read available data (non-blocking) - use os.read() directly on FD
            # to avoid blocking even with O_NONBLOCK set on the descriptor
            # Note: We read in larger chunks for efficiency, but only process ONE
            # command per reactor loop iteration via received_async() to match sync behavior
            fd = self._get_stdout(process_name).fileno()
            raw_data = os.read(fd, 16384)
            buf = str(raw_data, 'ascii')

            if buf == '' and poll is not None:
                # Process exited - EOF received
                # CRITICAL: Remove reader BEFORE calling _handle_problem to avoid race
                if self._async_mode and self._loop:
                    try:
                        self._loop.remove_reader(fd)
                        log.debug(
                            lazymsg('async.reader.removed.exit process={p} fd={fd}', p=process_name, fd=fd), 'processes'
                        )
                    except (ValueError, OSError):
                        pass  # Already removed or FD closed
                self._handle_problem(process_name)
                return

            # Buffer incomplete lines
            raw = self._buffer.get(process_name, '') + buf

            # Extract complete lines and queue as commands
            # Note: We queue all available commands here, but received_async() will
            # yield them ONE at a time to ensure proper interleaving with message sending
            while '\n' in raw:
                line, raw = raw.split('\n', 1)
                line = line.rstrip()

                if line.startswith('debug '):
                    log.warning(
                        lazymsg('api.debug.received process={pn} info={info}', pn=process_name, info=line[6:]), 'api'
                    )
                else:
                    log.debug(
                        lazymsg('api.command.received process={pn} command={ln}', pn=process_name, ln=line), 'processes'
                    )
                    # Queue command for processing
                    self._command_queue.append((process_name, formated(line)))

            self._buffer[process_name] = raw

            # Check if process exited
            if poll is not None:
                # CRITICAL: Remove reader BEFORE calling _handle_problem to avoid race
                if self._async_mode and self._loop:
                    try:
                        self._loop.remove_reader(fd)
                        log.debug(
                            lazymsg('async.reader.removed.exit process={p} fd={fd}', p=process_name, fd=fd), 'processes'
                        )
                    except (ValueError, OSError):
                        pass  # Already removed or FD closed
                self._handle_problem(process_name)

        except OSError as exc:
            # On error, try to remove reader to prevent callback loop
            try:
                if self._async_mode and self._loop and process_name in self._process:
                    proc_stdout = self._process[process_name].stdout
                    if proc_stdout is not None:
                        self._loop.remove_reader(proc_stdout.fileno())
                        log.debug(
                            lazymsg('async.reader.removed.error process={p} reason=oserror', p=process_name),
                            'processes',
                        )
            except (ValueError, OSError, AttributeError):
                pass

            if not exc.errno or exc.errno in error.fatal:
                self._handle_problem(process_name)
            elif exc.errno not in error.block:
                log.debug(lazymsg('process.error.unexpected errno={errstr}', errstr=errstr(exc)), 'processes')
        except (KeyError, AttributeError, UnicodeDecodeError) as exc:
            # On any exception, try to remove reader to prevent callback loop
            try:
                if self._async_mode and self._loop and process_name in self._process:
                    proc_stdout = self._process[process_name].stdout
                    if proc_stdout is not None:
                        self._loop.remove_reader(proc_stdout.fileno())
                        log.debug(
                            lazymsg('async.reader.removed.error process={p} reason=exception', p=process_name),
                            'processes',
                        )
            except (ValueError, OSError, AttributeError):
                pass

            log.debug(lazymsg('async.reader.exception process={p} error={e}', p=process_name, e=exc), 'processes')
            self._handle_problem(process_name)

    def received_async(self) -> Generator[Tuple[str, str], None, None]:
        """Async-compatible version of received() that yields buffered commands

        In async mode, commands are read by callbacks registered with the event
        loop and buffered in _command_queue. This method yields them one at a time
        to match sync version behavior and ensure commands are interleaved with
        message sending.

        CRITICAL: Only yield ONE command per call to match sync version, which
        polls and returns one command at a time. This ensures proper interleaving.

        Yields:
            Tuple of (process_name, command) for each buffered command
        """
        # Yield only ONE buffered command (matches sync version behavior)
        if self._command_queue:
            yield self._command_queue.popleft()

    def write(self, process: str, string: str | None, peer_or_neighbor: 'Neighbor' | 'Peer' | None = None) -> bool:
        if string is None:
            return True

        if process not in self._process:
            return False

        # Log API command response
        # Use warning level (like 'debug' commands from processes) to make it visible
        # when debug logging is enabled, especially for JSON/content responses
        from exabgp.reactor.api.response.answer import Answer

        # Check if this is a simple acknowledgment (done/error/shutdown in text or JSON)
        is_simple_ack = string in (
            Answer.text_done,
            Answer.text_error,
            Answer.text_shutdown,
            Answer.json_done,
            Answer.json_error,
            Answer.json_shutdown,
        )

        if is_simple_ack:
            # Simple ACK - use debug level
            log.debug(lazymsg('api.response.ack process={p} response={r}', p=process, r=string), 'processes')
        else:
            # Content response (JSON, text data, etc.) - use warning level to match
            # the visibility of 'debug' commands from external processes
            log.warning(lazymsg('api.response.content process={p} response={r}', p=process, r=string), 'api')

        data = bytes(f'{string}\n', 'ascii')

        # In async mode, queue the write instead of blocking
        if self._async_mode:
            if process not in self._write_queue:
                self._write_queue[process] = collections.deque()
            self._write_queue[process].append(data)
            log.debug(lazymsg('async.write.queued process={p} bytes={b}', p=process, b=len(data)), 'processes')
            return True

        # Sync mode - blocking write to subprocess stdin
        # Note: This can block if the pipe buffer is full and the subprocess isn't reading.
        # This is inherent to sync mode. Use async mode (exabgp_reactor_asyncio=true) for
        # non-blocking writes via the write queue mechanism above.
        stdin = self._get_stdin(process)
        while True:
            try:
                stdin.write(data)
            except OSError as exc:
                self._broken.append(process)
                if exc.errno == errno.EPIPE:
                    self._broken.append(process)
                    log.debug(lazymsg('process.write.failed reason=broken_pipe'), 'processes')
                    raise ProcessError from None
                else:
                    # Could it have been caused by a signal ? What to do.
                    log.debug(
                        lazymsg('process.write.error error={e} action=retry', e=errstr(exc)),
                        'processes',
                    )
                    continue
            break

        try:
            stdin.flush()
        except OSError as exc:
            # AFAIK, the buffer should be flushed at the next attempt.
            log.debug(
                lazymsg('process.flush.error error={e} action=retry', e=errstr(exc)),
                'processes',
            )

        return True

    async def write_async(self, process: str, string: str | None, neighbor: 'Neighbor' | None = None) -> bool:
        """Async version of write() - non-blocking write to API process stdin

        Uses os.write() on non-blocking fd to write without blocking the event loop.
        This prevents deadlock in async mode where blocking write would prevent
        reading from API process stdout.

        Note: Currently unused - async writes go through write() + flush_write_queue_async().
        Kept for potential future direct async write needs.
        """
        if string is None:
            return True

        if process not in self._process:
            return False

        # Log API command response
        # Use warning level (like 'debug' commands from processes) to make it visible
        # when debug logging is enabled, especially for JSON/content responses
        from exabgp.reactor.api.response.answer import Answer

        # Check if this is a simple acknowledgment (done/error/shutdown in text or JSON)
        is_simple_ack = string in (
            Answer.text_done,
            Answer.text_error,
            Answer.text_shutdown,
            Answer.json_done,
            Answer.json_error,
            Answer.json_shutdown,
        )

        if is_simple_ack:
            # Simple ACK - use debug level
            log.debug(lazymsg('api.response.ack process={p} response={r}', p=process, r=string), 'processes')
        else:
            # Content response (JSON, text data, etc.) - use warning level to match
            # the visibility of 'debug' commands from external processes
            log.warning(lazymsg('api.response.content process={p} response={r}', p=process, r=string), 'api')

        data = bytes(f'{string}\n', 'ascii')

        # Get stdin file descriptor (non-blocking, set in _start())
        stdin_fd = self._get_stdin(process).fileno()

        try:
            # Use os.write for non-blocking write (same as flush_write_queue_async)
            written = os.write(stdin_fd, data)
            if written < len(data):
                # Partial write - queue remainder for later flush
                if process not in self._write_queue:
                    self._write_queue[process] = collections.deque()
                self._write_queue[process].append(data[written:])
        except OSError as exc:
            self._broken.append(process)
            if exc.errno == errno.EAGAIN or exc.errno == errno.EWOULDBLOCK:
                # Buffer full - queue for later
                if process not in self._write_queue:
                    self._write_queue[process] = collections.deque()
                self._write_queue[process].append(data)
            elif exc.errno == errno.EPIPE:
                log.debug(lazymsg('process.write.failed reason=broken_pipe'), 'processes')
                raise ProcessError from None
            else:
                log.debug(
                    lazymsg('process.write.error error={e}', e=errstr(exc)),
                    'processes',
                )
                raise ProcessError from None

        return True

    async def flush_write_queue_async(self) -> None:
        """Flush all queued writes to API processes (async mode only)

        Called by main loop to drain the write queue without blocking.
        """
        if not self._async_mode:
            return

        # Debug: Log queue status
        if self._write_queue:
            for p, q in self._write_queue.items():
                if q:
                    log.debug(lazymsg('async.queue.flushing process={pn} items={cnt}', pn=p, cnt=len(q)), 'processes')

        for process_name in list(self._write_queue.keys()):
            if process_name not in self._process:
                # Process terminated, clear its queue
                del self._write_queue[process_name]
                continue

            queue = self._write_queue[process_name]
            if not queue:
                continue

            # Get stdin FD
            try:
                stdin_fd = self._get_stdin(process_name).fileno()
            except (AttributeError, ValueError):
                # Stdin closed or invalid
                log.debug(
                    lazymsg('async.queue.flush.failed process={p} reason=stdin_closed', p=process_name), 'processes'
                )
                del self._write_queue[process_name]
                continue

            # Write all queued data using os.write (non-blocking)
            while queue:
                data = queue.popleft()
                try:
                    # Use os.write for non-blocking write
                    log.debug(
                        lazymsg(
                            'async.write.attempt process={p} fd={fd} bytes={b}',
                            p=process_name,
                            fd=stdin_fd,
                            b=len(data),
                        ),
                        'processes',
                    )
                    written = os.write(stdin_fd, data)
                    log.debug(
                        lazymsg('async.write.result process={p} written={w}', p=process_name, w=written), 'processes'
                    )
                    if written < len(data):
                        # Partial write - put remaining data back
                        queue.appendleft(data[written:])
                        log.debug(
                            lazymsg(
                                'async.write.partial process={p} written={w} total={t}',
                                p=process_name,
                                w=written,
                                t=len(data),
                            ),
                            'processes',
                        )
                        break
                    log.debug(
                        lazymsg('async.write.flushed process={p} bytes={b}', p=process_name, b=written), 'processes'
                    )
                except OSError as exc:
                    if exc.errno == errno.EAGAIN or exc.errno == errno.EWOULDBLOCK:
                        # Buffer full, put data back and try next iteration
                        queue.appendleft(data)
                        log.debug(
                            lazymsg('async.write.deferred process={p} reason=buffer_full', p=process_name), 'processes'
                        )
                        break
                    elif exc.errno == errno.EPIPE:
                        # Broken pipe - process died
                        self._broken.append(process_name)
                        log.debug(
                            lazymsg('async.write.failed process={p} reason=broken_pipe', p=process_name), 'processes'
                        )
                        del self._write_queue[process_name]
                        break
                    else:
                        # Other error
                        self._broken.append(process_name)
                        log.debug(
                            lazymsg('async.queue.flush.error process={pn} error={e}', pn=process_name, e=errstr(exc)),
                            'processes',
                        )
                        del self._write_queue[process_name]
                        break

    def _answer(self, service: str, string: str, force: bool = False) -> None:
        # Check per-process ACK state
        process_ack = self._ack[service]
        if force or process_ack:
            # NOTE: Do not convert to f-string! F-strings with backslash escapes in
            # expressions (like \n in .replace()) require Python 3.12+.
            # This project supports Python 3.8+, so we must use % formatting.
            log.debug(
                lazymsg('api.answer service={s} response={r}', s=service, r=string.replace('\n', '\\n')), 'processes'
            )
            self.write(service, string)

    async def _answer_async(self, service: str, string: str, force: bool = False) -> None:
        """Async version of _answer() - non-blocking response to API process

        Queues the write and flushes immediately to ensure response delivered
        before callback returns (prevents race condition).
        """
        process_ack = self._ack[service]
        if force or process_ack:
            log.debug(
                lazymsg('api.answer.async service={s} response={r}', s=service, r=string.replace('\n', '\\n')),
                'processes',
            )
            self.write(service, string)  # Queue write
            await self.flush_write_queue_async()  # Flush immediately

    def answer_done(self, service: str, force: bool = False) -> None:
        """Send ACK/done response to API process

        In async mode, this returns a coroutine that must be awaited.
        In sync mode, this blocks until write completes.
        """
        # In async mode, caller must use answer_done_async() instead
        # This sync version will block and cause deadlock in async mode
        if self._async_mode:
            # This should not be called in async mode - caller should use answer_done_async()
            # But for compatibility during migration, we can detect this
            log.warning(
                lazymsg('api.answer.mode.mismatch service={s} mode=async expected=answer_done_async', s=service),
                'processes',
            )

        if self._ackjson[service]:
            self._answer(service, Answer.json_done, force=force)
        else:
            self._answer(service, Answer.text_done, force=force)

    async def answer_done_async(self, service: str, force: bool = False) -> None:
        """Async version of answer_done() - non-blocking ACK to API process

        Queues the write and flushes immediately to ensure ACK delivered
        before callback returns (prevents race condition).
        """
        log.debug(lazymsg('api.answer.done.async service={s}', s=service), 'processes')
        if self._ackjson[service]:
            self._answer(service, Answer.json_done, force=force)
        else:
            self._answer(service, Answer.text_done, force=force)
        # Flush immediately to ensure ACK delivered before callback returns
        log.debug(lazymsg('api.flush.async.start service={s}', s=service), 'processes')
        await self.flush_write_queue_async()
        log.debug(lazymsg('api.flush.async.complete service={s}', s=service), 'processes')

    def answer_error(self, service: str, message: str = '') -> None:
        """Send error response, optionally with descriptive message"""
        if message:
            # Send error details before the error marker
            if self._ackjson[service]:
                import json

                error_data = {'error': message}
                self._answer(service, json.dumps(error_data))
            else:
                self._answer(service, f'error: {message}')

        # Send standard error markers
        if self._ackjson[service]:
            self._answer(service, Answer.json_error)
            # Send error marker after JSON error for consistency with text API
            self._answer(service, Answer.text_error, force=True)
        else:
            self._answer(service, Answer.text_error)

    async def answer_error_async(self, service: str, message: str = '') -> None:
        """Async version of answer_error() - non-blocking error response to API process"""
        if message:
            # Send error details before the error marker
            if self._ackjson[service]:
                import json

                error_data = {'error': message}
                await self._answer_async(service, json.dumps(error_data))
            else:
                await self._answer_async(service, f'error: {message}')

        # Send standard error markers
        if self._ackjson[service]:
            await self._answer_async(service, Answer.json_error)
            # Send error marker after JSON error for consistency with text API
            await self._answer_async(service, Answer.text_error, force=True)
        else:
            await self._answer_async(service, Answer.text_error)

    def set_ack(self, service: str, enabled: bool) -> None:
        """Set ACK state for a specific service/process"""
        self._ack[service] = enabled
        log.debug(lazymsg('api.ack.set service={s} enabled={e}', s=service, e=enabled), 'processes')

    def get_ack(self, service: str) -> bool:
        """Get ACK state for a specific service/process"""
        return self._ack[service]

    def set_sync(self, service: str, enabled: bool) -> None:
        """Set sync mode for a specific service/process.

        When sync mode is enabled, API commands wait for routes to be
        flushed to wire before sending ACK response.
        """
        self._sync[service] = enabled
        log.debug(lazymsg('api.sync.set service={s} enabled={e}', s=service, e=enabled), 'processes')

    def get_sync(self, service: str) -> bool:
        """Get sync mode for a specific service/process (default: False)"""
        return self._sync.get(service, False)

    def _notify(self, peer_or_neighbor: 'Neighbor' | 'Peer', event: str) -> Generator[str, None, None]:
        # Accept both Peer and Neighbor - Peer has .neighbor attribute
        # Use getattr with default to handle both types safely
        neighbor: 'Neighbor' = getattr(peer_or_neighbor, 'neighbor', peer_or_neighbor)  # type: ignore[arg-type,assignment]
        if neighbor.api is None:
            return
        for process in neighbor.api[event]:
            yield process

    # do not do anything if silenced
    # no-self-argument

    @staticmethod
    def silenced(function: _F) -> _F:
        def closure(self: 'Processes', *args: Any, **kwargs: Any) -> None:
            if self.silence:
                return None
            return function(self, *args, **kwargs)

        return cast(_F, closure)

    # invalid-name
    @silenced
    def up(self, neighbor: 'Neighbor') -> None:
        for process in self._notify(neighbor, 'neighbor-changes'):
            self.write(process, self._encoder[process].up(neighbor), neighbor)

    @silenced
    def connected(self, neighbor: 'Neighbor') -> None:
        for process in self._notify(neighbor, 'neighbor-changes'):
            self.write(process, self._encoder[process].connected(neighbor), neighbor)

    @silenced
    def down(self, neighbor: 'Neighbor', reason: str) -> None:
        for process in self._notify(neighbor, 'neighbor-changes'):
            self.write(process, self._encoder[process].down(neighbor, reason), neighbor)

    @silenced
    def negotiated(self, neighbor: 'Neighbor', negotiated: Negotiated) -> None:
        for process in self._notify(neighbor, 'negotiated'):
            self.write(process, self._encoder[process].negotiated(neighbor, negotiated), neighbor)

    @silenced
    def fsm(self, neighbor: 'Neighbor', fsm: 'FSM') -> None:
        for process in self._notify(neighbor, 'fsm'):
            self.write(process, self._encoder[process].fsm(neighbor, fsm), neighbor)

    @silenced
    def signal(self, neighbor: 'Neighbor', signal: str) -> None:
        for process in self._notify(neighbor, 'signal'):
            self.write(process, self._encoder[process].signal(neighbor, signal), neighbor)

    @silenced
    def packets(
        self,
        neighbor: 'Neighbor',
        direction: str,
        category: int,
        header: bytes | str,
        body: bytes | str,
        negotiated: Negotiated | None = None,
    ) -> None:
        for process in self._notify(neighbor, '{}-packets'.format(direction)):
            self.write(
                process,
                self._encoder[process].packets(neighbor, direction, category, negotiated, header, body),
                neighbor,
            )

    @silenced
    def notification(
        self,
        neighbor: 'Neighbor',
        direction: str,
        message: 'Notify',
        header: bytes | str,
        body: bytes | str,
        negotiated: Negotiated | None = None,
    ) -> None:
        for process in self._notify(neighbor, 'neighbor-changes'):
            self.write(
                process,
                self._encoder[process].notification(neighbor, direction, message, header, body, negotiated),
                neighbor,
            )

    @silenced
    def message(
        self,
        message_id: int,
        neighbor: 'Neighbor',
        direction: str,
        message: Message,
        header: bytes | str,
        *body: bytes | str,
        negotiated: Negotiated | None = None,
    ) -> None:
        self._dispatch[message_id](self, neighbor, direction, message, negotiated, header, *body)

    # registering message functions
    # no-self-argument

    @staticmethod
    def register_process(
        message_id: int, storage: Dict[int, Any] = _dispatch
    ) -> Callable[[Callable[..., None]], Callable[..., None]]:
        def closure(function: Callable[..., None]) -> Callable[..., None]:
            def wrap(*args: Any) -> None:
                function(*args)

            storage[message_id] = wrap
            return wrap

        return closure

    # notifications are handled in the loop as they use different arguments

    @register_process(Message.CODE.OPEN)
    def _open(
        self, peer: 'Peer', direction: str, message: 'Open', negotiated: Negotiated, header: str, body: str
    ) -> None:
        for process in self._notify(peer, f'{direction}-{Message.CODE.OPEN.SHORT}'):
            self.write(process, self._encoder[process].open(peer, direction, message, negotiated, header, body), peer)

    @register_process(Message.CODE.UPDATE)
    def _update(
        self, peer: 'Peer', direction: str, update: 'Update', negotiated: Negotiated, header: str, body: str
    ) -> None:
        for process in self._notify(peer, f'{direction}-{Message.CODE.UPDATE.SHORT}'):
            self.write(process, self._encoder[process].update(peer, direction, update, negotiated, header, body), peer)

    @register_process(Message.CODE.NOTIFICATION)
    def _notification(
        self, peer: 'Peer', direction: str, message: Any, negotiated: Negotiated, header: str, body: str
    ) -> None:
        for process in self._notify(peer, f'{direction}-{Message.CODE.NOTIFICATION.SHORT}'):
            self.write(
                process,
                self._encoder[process].notification(peer, direction, message, negotiated, header, body),
                peer,
            )

    # unused-argument, must keep the API
    @register_process(Message.CODE.KEEPALIVE)
    def _keepalive(
        self, peer: 'Peer', direction: str, keepalive: Any, negotiated: Negotiated, header: str, body: str
    ) -> None:
        for process in self._notify(peer, f'{direction}-{Message.CODE.KEEPALIVE.SHORT}'):
            self.write(process, self._encoder[process].keepalive(peer, direction, negotiated, header, body), peer)

    @register_process(Message.CODE.ROUTE_REFRESH)
    def _refresh(
        self, peer: 'Peer', direction: str, refresh: Any, negotiated: Negotiated, header: str, body: str
    ) -> None:
        for process in self._notify(peer, f'{direction}-{Message.CODE.ROUTE_REFRESH.SHORT}'):
            self.write(
                process,
                self._encoder[process].refresh(peer, direction, refresh, negotiated, header, body),
                peer,
            )

    @register_process(Message.CODE.OPERATIONAL)
    def _operational(
        self, peer: 'Peer', direction: str, operational: Any, negotiated: Negotiated, header: str, body: str
    ) -> None:
        for process in self._notify(peer, f'{direction}-{Message.CODE.OPERATIONAL.SHORT}'):
            self.write(
                process,
                self._encoder[process].operational(
                    peer,
                    direction,
                    operational.category,
                    operational,
                    negotiated,
                    header,
                    body,
                ),
                peer,
            )
