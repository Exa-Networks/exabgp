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

from typing import Any, Dict, Generator, List, Optional, Tuple, Union, TYPE_CHECKING
from threading import Thread

if TYPE_CHECKING:
    from exabgp.bgp.neighbor import Neighbor
    from exabgp.reactor.peer import Peer
    from exabgp.bgp.message import Open, Update
    from exabgp.bgp.fsm import FSM

from exabgp.util.errstr import errstr
from exabgp.reactor.network.error import error

from exabgp.configuration.core.format import formated
from exabgp.reactor.api.response import Response
from exabgp.reactor.api.response.answer import Answer

from exabgp.bgp.message import Message
from exabgp.bgp.message.open.capability import Negotiated
from exabgp.logger import log

from exabgp.version import json as json_version
from exabgp.version import text as text_version

from exabgp.environment import getenv


# pylint: disable=no-self-argument,not-callable,unused-argument,invalid-name


class ProcessError(Exception):
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

    def number(self) -> int:
        return len(self._process)

    def clean(self) -> None:
        self.fds: List[int] = []
        self._process: Dict[str, subprocess.Popen[bytes]] = {}
        self._encoder: Dict[str, Union[Response.JSON, Response.Text]] = {}
        self._ackjson: Dict[str, bool] = {}
        self._ack: Dict[str, bool] = {}
        self._broken: List[str] = []
        self._respawning: Dict[str, Dict[int, int]] = {}

    def _handle_problem(self, process: str) -> None:
        if process not in self._process:
            return
        if self.respawn_number and self._restart[process]:
            log.debug(lambda: f'process {process} ended, restarting it', 'process')
            self._terminate(process)
            self._start(process)
        else:
            log.debug(lambda: f'process {process} ended', 'process')
            self._terminate(process)

    def _terminate(self, process_name: str) -> Thread:
        log.debug(lambda: f'terminating process {process_name}', 'process')
        process = self._process[process_name]
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
                log.debug(lambda: f'force kill unresponsive {process_name}', 'process')
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
                log.debug(lambda process=process: f'child process {process} was already dead', 'process')
        self.clean()

    def _start(self, process: str) -> None:
        if not self._restart.get(process, True):
            return

        try:
            if process in self._process:
                log.debug(lambda: 'process already running', 'process')
                return

            if process not in self._configuration:
                log.debug(lambda: 'can not start process, no configuration for it', 'process')
                return
            # Prevent some weird termcap data to be created at the start of the PIPE
            # \x1b[?1034h (no-eol) (esc)
            os.environ['TERM'] = 'dumb'

            configuration = self._configuration[process]

            run = configuration.get('run', '')
            if run:
                use_json = configuration.get('encoder', 'text') == 'json'
                self._encoder[process] = Response.JSON(json_version) if use_json else Response.Text(text_version)
                # XXX: add an option to ack in JSON (do not break backward compatibility)
                self._ackjson[process] = False
                # Initialize per-process ACK state (process config overrides global default)
                self._ack[process] = configuration.get('ack', self._default_ack)

                self._process[process] = subprocess.Popen(
                    run,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    preexec_fn=preexec_helper,
                    # This flags exists for python 2.7.3 in the documentation but on on my MAC
                    # creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
                )
                self._update_fds()
                fcntl.fcntl(self._process[process].stdout.fileno(), fcntl.F_SETFL, os.O_NONBLOCK)  # type: ignore[union-attr]

                log.debug(lambda: 'forked process {}'.format(process), 'process')

                self._restart[process] = self._configuration[process]['respawn']
                around_now = int(time.time()) & self.respawn_timemask
                if process in self._respawning:
                    if around_now in self._respawning[process]:
                        self._respawning[process][around_now] += 1
                        # we are respawning too fast
                        if self._respawning[process][around_now] > self.respawn_number:
                            log.critical(
                                lambda: f'Too many death for {process} ({self.respawn_number}) terminating program',
                                'process',
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
            log.debug(lambda: 'could not start process {}'.format(process), 'process')
            log.debug(lambda exc=exc: 'reason: {}'.format(str(exc)), 'process')

    def start(self, configuration: Dict[str, Dict[str, Any]], restart: bool = False) -> None:
        for process in list(self._process):
            if process not in configuration:
                self._terminate(process)
        self._configuration = configuration
        for process in configuration:
            if process in list(self._process):
                if restart:
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

    def _update_fds(self) -> None:
        self.fds = [self._process[process].stdout.fileno() for process in self._process]  # type: ignore[union-attr]

    def received(self) -> Generator[Tuple[str, str], None, None]:
        consumed_data = False

        for process in list(self._process):
            try:
                proc = self._process[process]
                poll = proc.poll()

                poller = select.poll()
                poller.register(
                    proc.stdout,
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
                    buf = str(proc.stdout.read(16384), 'ascii')  # type: ignore[union-attr]
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
                                lambda line=line, process=process: f'debug info from {process} : {line[6:]} ', 'api'
                            )
                        else:
                            log.debug(
                                lambda line=line, process=process: f'command from process {process} : {line} ',
                                'process',
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
                            lambda exc=exc: f'unexpected errno received from forked process ({errstr(exc)})', 'process'
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

    def write(self, process: str, string: Optional[str], neighbor: Optional['Neighbor'] = None) -> bool:
        if string is None:
            return True

        # XXX: FIXME: This is potentially blocking
        while True:
            try:
                self._process[process].stdin.write(bytes(f'{string}\n', 'ascii'))  # type: ignore[union-attr]
            except OSError as exc:
                self._broken.append(process)
                if exc.errno == errno.EPIPE:
                    self._broken.append(process)
                    log.debug(lambda: 'issue while sending data to our helper program', 'process')
                    raise ProcessError from None
                else:
                    # Could it have been caused by a signal ? What to do.
                    log.debug(
                        lambda exc=exc: f'error received while sending data to helper program, retrying ({errstr(exc)})',
                        'process',
                    )
                    continue
            break

        try:
            self._process[process].stdin.flush()  # type: ignore[union-attr]
        except OSError as exc:
            # AFAIK, the buffer should be flushed at the next attempt.
            log.debug(
                lambda exc=exc: f'error received while FLUSHING data to helper program, retrying ({errstr(exc)})',
                'process',
            )

        return True

    def _answer(self, service: str, string: str, force: bool = False) -> None:
        # Check per-process ACK state
        process_ack = self._ack[service]
        if force or process_ack:
            # NOTE: Do not convert to f-string! F-strings with backslash escapes in
            # expressions (like \n in .replace()) require Python 3.12+.
            # This project supports Python 3.8+, so we must use % formatting.
            log.debug(lambda: 'responding to {} : {}'.format(service, string.replace('\n', '\\n')), 'process')
            self.write(service, string)

    def answer_done(self, service: str, force: bool = False) -> None:
        if self._ackjson[service]:
            self._answer(service, Answer.json_done, force=force)
        else:
            self._answer(service, Answer.text_done, force=force)

    def answer_error(self, service: str) -> None:
        if self._ackjson[service]:
            self._answer(service, Answer.json_error)
        else:
            self._answer(service, Answer.text_error)

    def set_ack(self, service: str, enabled: bool) -> None:
        """Set ACK state for a specific service/process"""
        self._ack[service] = enabled
        log.debug(lambda: 'ACK {} for {}'.format('enabled' if enabled else 'disabled', service), 'process')

    def get_ack(self, service: str) -> bool:
        """Get ACK state for a specific service/process"""
        return self._ack[service]

    def _notify(self, neighbor: 'Neighbor', event: str) -> Generator[str, None, None]:
        for process in neighbor.api[event]:
            yield process

    # do not do anything if silenced
    # no-self-argument

    def silenced(function):
        def closure(self, *args):
            if self.silence:
                return None
            return function(self, *args)

        return closure

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
        self, neighbor: 'Neighbor', direction: str, category: int, negotiated: Negotiated, header: str, body: str
    ) -> None:
        for process in self._notify(neighbor, '{}-packets'.format(direction)):
            self.write(
                process,
                self._encoder[process].packets(neighbor, direction, category, negotiated, header, body),
                neighbor,
            )

    @silenced
    def notification(
        self, neighbor: 'Neighbor', direction: str, code: int, subcode: int, data: str, header: str, body: str
    ) -> None:
        for process in self._notify(neighbor, 'neighbor-changes'):
            self.write(
                process,
                self._encoder[process].notification(neighbor, direction, code, subcode, data, header, body),
                neighbor,
            )

    @silenced
    def message(
        self,
        message_id: int,
        neighbor: 'Neighbor',
        direction: str,
        message: Message,
        negotiated: Negotiated,
        header: str,
        *body: str,
    ) -> None:
        self._dispatch[message_id](self, neighbor, direction, message, negotiated, header, *body)

    # registering message functions
    # no-self-argument

    def register_process(message_id: int, storage: Dict[int, Any] = _dispatch):
        def closure(function):
            def wrap(*args):
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
        self, peer: Any, direction: str, message: Any, negotiated: Negotiated, header: str, body: str
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
        self, peer: Any, direction: str, keepalive: Any, negotiated: Negotiated, header: str, body: str
    ) -> None:
        for process in self._notify(peer, f'{direction}-{Message.CODE.KEEPALIVE.SHORT}'):
            self.write(process, self._encoder[process].keepalive(peer, direction, negotiated, header, body), peer)

    @register_process(Message.CODE.ROUTE_REFRESH)
    def _refresh(self, peer: Any, direction: str, refresh: Any, negotiated: Negotiated, header: str, body: str) -> None:
        for process in self._notify(peer, f'{direction}-{Message.CODE.ROUTE_REFRESH.SHORT}'):
            self.write(
                process,
                self._encoder[process].refresh(peer, direction, refresh, negotiated, header, body),
                peer,
            )

    @register_process(Message.CODE.OPERATIONAL)
    def _operational(
        self, peer: Any, direction: str, operational: Any, negotiated: Negotiated, header: str, body: str
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
