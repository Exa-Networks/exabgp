"""
process.py

Created by Thomas Mangin on 2011-05-02.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

import os
import errno
import time
import subprocess
import select
import fcntl

from exabgp.util import str_ascii
from exabgp.util import bytes_ascii
from exabgp.util.errstr import errstr
from exabgp.reactor.network.error import error

from exabgp.configuration.core.format import formated
from exabgp.reactor.api.response import Response
from exabgp.reactor.api.response.answer import Answer

from exabgp.bgp.message import Message
from exabgp.logger import Logger

from exabgp.version import json as json_version
from exabgp.version import text as text_version

from exabgp.configuration.environment import environment
from threading import Thread


# pylint: disable=no-self-argument,not-callable,unused-argument,invalid-name


class ProcessError(Exception):
    pass


def preexec_helper():
    # make this process a new process group
    # os.setsid()
    # This prevent the signal to be sent to the children (and create a new process group)
    os.setpgrp()
    # signal.signal(signal.SIGINT, signal.SIG_IGN)


class Processes(object):
    # how many time can a process can respawn in the time interval
    respawn_timemask = 0xFFFFFF - 0b111111
    # '0b111111111111111111000000' (around a minute, 63 seconds)

    _dispatch = {}

    def __init__(self):
        self.logger = Logger()
        self.clean()
        self.silence = False
        self._buffer = {}
        self._configuration = {}
        self._restart = {}

        self.respawn_number = 5 if environment.settings().api.respawn else 0
        self.terminate_on_error = environment.settings().api.terminate
        self.ack = environment.settings().api.ack

    def number(self):
        return len(self._process)

    def clean(self):
        self.fds = []
        self._process = {}
        self._encoder = {}
        self._broken = []
        self._respawning = {}

    def _handle_problem(self, process):
        if process not in self._process:
            return
        if self.respawn_number and self._restart[process]:
            self.logger.debug('process %s ended, restarting it' % process, 'process')
            self._terminate(process)
            self._start(process)
        else:
            self.logger.debug('process %s ended' % process, 'process')
            self._terminate(process)

    def _terminate(self, process_name):
        self.logger.debug('terminating process %s' % process_name, 'process')
        process = self._process[process_name]
        del self._process[process_name]
        self._update_fds()
        thread = Thread(target=self._terminate_run, args=(process,))
        thread.start()
        return thread

    def _terminate_run(self, process):
        try:
            process.terminate()
            process.wait()
        except (OSError, KeyError):
            # the process is most likely already dead
            pass

    def terminate(self):
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
                self.logger.debug('child process %s was already dead' % process, 'process')
        self.clean()

    def _start(self, process):
        if not self._restart.get(process, True):
            return

        try:

            if process in self._process:
                self.logger.debug('process already running', 'process')
                return

            if process not in self._configuration:
                self.logger.debug('can not start process, no configuration for it', 'process')
                return
            # Prevent some weird termcap data to be created at the start of the PIPE
            # \x1b[?1034h (no-eol) (esc)
            os.environ['TERM'] = 'dumb'

            configuration = self._configuration[process]

            run = configuration.get('run', '')
            if run:
                api = configuration.get('encoder', '')
                self._encoder[process] = Response.Text(text_version) if api == 'text' else Response.JSON(json_version)

                self._process[process] = subprocess.Popen(
                    run,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    preexec_fn=preexec_helper
                    # This flags exists for python 2.7.3 in the documentation but on on my MAC
                    # creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
                )
                self._update_fds()
                fcntl.fcntl(self._process[process].stdout.fileno(), fcntl.F_SETFL, os.O_NONBLOCK)

                self.logger.debug('forked process %s' % process, 'process')

                self._restart[process] = self._configuration[process]['respawn']
                around_now = int(time.time()) & self.respawn_timemask
                if process in self._respawning:
                    if around_now in self._respawning[process]:
                        self._respawning[process][around_now] += 1
                        # we are respawning too fast
                        if self._respawning[process][around_now] > self.respawn_number:
                            self.logger.critical(
                                'Too many death for %s (%d) terminating program' % (process, self.respawn_number),
                                'process',
                            )
                            raise ProcessError()
                    else:
                        # reset long time since last respawn
                        self._respawning[process] = {around_now: 1}
                else:
                    # record respawing
                    self._respawning[process] = {around_now: 1}

        except (subprocess.CalledProcessError, OSError, ValueError) as exc:
            self._broken.append(process)
            self.logger.debug('could not start process %s' % process, 'process')
            self.logger.debug('reason: %s' % str(exc), 'process')

    def start(self, configuration, restart=False):
        for process in list(self._process):
            if process not in configuration:
                self._terminate(process)
        self._configuration = configuration
        for process in configuration:
            if restart and process in list(self._process):
                self._terminate(process)
            self._start(process)

    def broken(self, neighbor):
        if self._broken:
            for process in self._configuration:
                if process in self._broken:
                    return True
        return False

    def _update_fds(self):
        self.fds = [self._process[process].stdout.fileno() for process in self._process]

    def received(self):
        consumed_data = False

        for process in list(self._process):
            try:
                proc = self._process[process]
                poll = proc.poll()

                poller = select.poll()
                poller.register(
                    proc.stdout, select.POLLIN | select.POLLPRI | select.POLLHUP | select.POLLNVAL | select.POLLERR
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
                    buf = str_ascii(proc.stdout.read(16384))
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
                        self.logger.debug('command from process %s : %s ' % (process, line), 'process')
                        yield (process, formated(line))

                    self._buffer[process] = raw

                except IOError as exc:
                    if not exc.errno or exc.errno in error.fatal:
                        # if the program exits we can get an IOError with errno code zero !
                        self._handle_problem(process)
                    elif exc.errno in error.block:
                        # we often see errno.EINTR: call interrupted and
                        # we most likely have data, we will try to read them a the next loop iteration
                        pass
                    else:
                        self.logger.debug('unexpected errno received from forked process (%s)' % errstr(exc), 'process')
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

    def write(self, process, string, neighbor=None):
        if string is None:
            return True

        # XXX: FIXME: This is potentially blocking
        while True:
            try:
                self._process[process].stdin.write(bytes_ascii('%s\n' % string))
            except IOError as exc:
                self._broken.append(process)
                if exc.errno == errno.EPIPE:
                    self._broken.append(process)
                    self.logger.debug('issue while sending data to our helper program', 'process')
                    raise ProcessError()
                else:
                    # Could it have been caused by a signal ? What to do.
                    self.logger.debug(
                        'error received while sending data to helper program, retrying (%s)' % errstr(exc), 'process'
                    )
                    continue
            break

        try:
            self._process[process].stdin.flush()
        except IOError as exc:
            # AFAIK, the buffer should be flushed at the next attempt.
            self.logger.debug(
                'error received while FLUSHING data to helper program, retrying (%s)' % errstr(exc), 'process'
            )

        return True

    def _answer(self, service, string, force=False):
        if force or self.ack:
            self.logger.debug('responding to %s : %s' % (service, string.replace('\n', '\\n')), 'process')
            self.write(service, string)

    def answer_done(self, service):
        self._answer(service, Answer.done)

    def answer_error(self, service):
        self._answer(service, Answer.error)

    def _notify(self, neighbor, event):
        for process in neighbor.api[event]:
            yield process

    # do not do anything if silenced
    # no-self-argument

    def silenced(function):
        def closure(self, *args):
            if self.silence:
                return
            return function(self, *args)

        return closure

    # invalid-name
    @silenced
    def up(self, neighbor):
        for process in self._notify(neighbor, 'neighbor-changes'):
            self.write(process, self._encoder[process].up(neighbor), neighbor)

    @silenced
    def connected(self, neighbor):
        for process in self._notify(neighbor, 'neighbor-changes'):
            self.write(process, self._encoder[process].connected(neighbor), neighbor)

    @silenced
    def down(self, neighbor, reason):
        for process in self._notify(neighbor, 'neighbor-changes'):
            self.write(process, self._encoder[process].down(neighbor, reason), neighbor)

    @silenced
    def negotiated(self, neighbor, negotiated):
        for process in self._notify(neighbor, 'negotiated'):
            self.write(process, self._encoder[process].negotiated(neighbor, negotiated), neighbor)

    @silenced
    def fsm(self, neighbor, fsm):
        for process in self._notify(neighbor, 'fsm'):
            self.write(process, self._encoder[process].fsm(neighbor, fsm), neighbor)

    @silenced
    def signal(self, neighbor, signal):
        for process in self._notify(neighbor, 'signal'):
            self.write(process, self._encoder[process].signal(neighbor, signal), neighbor)

    @silenced
    def packets(self, neighbor, direction, category, negotiated, header, body):
        for process in self._notify(neighbor, '%s-packets' % direction):
            self.write(
                process,
                self._encoder[process].packets(neighbor, direction, category, negotiated, header, body),
                neighbor,
            )

    @silenced
    def notification(self, neighbor, direction, code, subcode, data, header, body):
        for process in self._notify(neighbor, 'neighbor-changes'):
            self.write(
                process,
                self._encoder[process].notification(neighbor, direction, code, subcode, data, header, body),
                neighbor,
            )

    @silenced
    def message(self, message_id, neighbor, direction, message, negotiated, header, *body):
        self._dispatch[message_id](self, neighbor, direction, message, negotiated, header, *body)

    # registering message functions
    # no-self-argument

    def register_process(message_id, storage=_dispatch):
        def closure(function):
            def wrap(*args):
                function(*args)

            storage[message_id] = wrap
            return wrap

        return closure

    # notifications are handled in the loop as they use different arguments

    @register_process(Message.CODE.OPEN)
    def _open(self, peer, direction, message, negotiated, header, body):
        for process in self._notify(peer, '%s-%s' % (direction, Message.CODE.OPEN.SHORT)):
            self.write(process, self._encoder[process].open(peer, direction, message, negotiated, header, body), peer)

    @register_process(Message.CODE.UPDATE)
    def _update(self, peer, direction, update, negotiated, header, body):
        for process in self._notify(peer, '%s-%s' % (direction, Message.CODE.UPDATE.SHORT)):
            self.write(process, self._encoder[process].update(peer, direction, update, negotiated, header, body), peer)

    @register_process(Message.CODE.NOTIFICATION)
    def _notification(self, peer, direction, message, negotiated, header, body):
        for process in self._notify(peer, '%s-%s' % (direction, Message.CODE.NOTIFICATION.SHORT)):
            self.write(
                process, self._encoder[process].notification(peer, direction, message, negotiated, header, body), peer
            )

    # unused-argument, must keep the API
    @register_process(Message.CODE.KEEPALIVE)
    def _keepalive(self, peer, direction, keepalive, negotiated, header, body):
        for process in self._notify(peer, '%s-%s' % (direction, Message.CODE.KEEPALIVE.SHORT)):
            self.write(process, self._encoder[process].keepalive(peer, direction, negotiated, header, body), peer)

    @register_process(Message.CODE.ROUTE_REFRESH)
    def _refresh(self, peer, direction, refresh, negotiated, header, body):
        for process in self._notify(peer, '%s-%s' % (direction, Message.CODE.ROUTE_REFRESH.SHORT)):
            self.write(
                process, self._encoder[process].refresh(peer, direction, refresh, negotiated, header, body), peer
            )

    @register_process(Message.CODE.OPERATIONAL)
    def _operational(self, peer, direction, operational, negotiated, header, body):
        for process in self._notify(peer, '%s-%s' % (direction, Message.CODE.OPERATIONAL.SHORT)):
            self.write(
                process,
                self._encoder[process].operational(
                    peer, direction, operational.category, operational, negotiated, header, body
                ),
                peer,
            )
