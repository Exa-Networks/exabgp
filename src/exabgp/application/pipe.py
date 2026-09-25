"""pipe.py

Created by Thomas Mangin on <unset>.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import contextlib
import os
import sys
import fcntl
import stat
import time
import signal
import select
import traceback
from exabgp.util.backlog import Backlog

from exabgp.reactor.network.error import error

kb = 1024
mb = kb * 1024

# a single API command must fit in one line, and the backlog is what we could not forward yet
MAX_COMMAND_SIZE = mb
MAX_BACKLOG_SIZE = 100 * mb


def named_pipe(root, pipename='exabgp'):
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
    for location in locations:
        cli_in = location + pipename + '.in'
        cli_out = location + pipename + '.out'

        try:
            if not stat.S_ISFIFO(os.stat(cli_in).st_mode):
                continue
            if not stat.S_ISFIFO(os.stat(cli_out).st_mode):
                continue
        except Exception:
            continue
        os.environ['exabgp_cli_pipe'] = location
        return [location]
    return locations


def env(app, section, name, default):
    r = os.environ.get(f'{app}.{section}.{name}', None)
    if r is None:
        r = os.environ.get(f'{app}_{section}_{name}', None)
    if r is None:
        return default
    return r


def check_fifo(name):
    """Report whether name is a named pipe this process can use, saying why when it is not.

    os.stat is the only call here which can fail. The three messages which used to follow
    it, 'could not create', 'could not access/delete' and 'could not write on', came with
    3482b2c93, which lifted them from the code which did call os.mkfifo, os.remove and
    sendall into a body which only stats. They were written as OSError, IOError and
    socket.error, one type since Python 3.3, so only the first ever ran: the other two
    described work this function does not do and returned None while doing it.

    What an operator needs told apart is not which call failed but which errno came back:
    nothing there at all, a directory on the way we may not search, or anything else.

    The report goes to stderr, not stdout, and that is not only convention here. One of the
    two callers is Control, where stdout IS the pipe to the daemon, so every one of these
    lines was written down that pipe and read by the daemon as a command line rather than by
    an operator as an error. The rest of this file already says so twice, at the two places
    which do use stderr; this function was the one which did not.
    """
    path = os.path.abspath(name)
    try:
        mode = os.stat(name).st_mode
    except FileNotFoundError:
        sys.stderr.write(f'error: could not find the named pipe {path}\n')
        sys.stderr.flush()
        return False
    except PermissionError:
        sys.stderr.write(f'error: not allowed to reach the named pipe {path}\n')
        sys.stderr.flush()
        return False
    except OSError as exc:
        sys.stderr.write(f'error: could not check the named pipe {path} ({exc.strerror})\n')
        sys.stderr.flush()
        return False

    if not stat.S_ISFIFO(mode):
        sys.stderr.write(f'error: a file exist which is not a named pipe ({path})\n')
        sys.stderr.flush()
        return False

    if not os.access(name, os.R_OK):
        sys.stderr.write(f'error: a named pipe exists and we can not read/write to it ({path})\n')
        sys.stderr.flush()
        return False

    return True


class Control:
    terminating = False

    def __init__(self, location):
        self.send = location + env('exabgp', 'api', 'pipename', 'exabgp') + '.out'
        self.recv = location + env('exabgp', 'api', 'pipename', 'exabgp') + '.in'
        self.r_pipe = None

    def init(self):
        # obviously this is vulnerable to race conditions ... if an attacker can create fifo in the folder

        if not check_fifo(self.recv):
            self.terminate()
            sys.exit(1)

        if not check_fifo(self.send):
            self.terminate()
            sys.exit(1)

        signal.signal(signal.SIGINT, self.terminate)
        signal.signal(signal.SIGTERM, self.terminate)
        return True

    def cleanup(self):
        def _close(pipe):
            if pipe:
                # We are tearing the process down, so a descriptor which refuses to close is
                # already as closed as we need it to be.
                with contextlib.suppress(OSError, TypeError):
                    os.close(pipe)

        _close(self.r_pipe)

    def terminate(self, ignore=None, me=None):
        # if the named pipe is open, and remove_fifo called
        # do not ignore a second signal
        if self.terminating:
            sys.exit(1)
        self.terminating = True

        self.cleanup()

    def read_on(self, reading):
        sleep_time = 1000

        poller = select.poll()
        for io in reading:
            if io is not None:
                poller.register(io, select.POLLIN | select.POLLPRI | select.POLLHUP | select.POLLNVAL | select.POLLERR)

        ready = []
        for io, event in poller.poll(sleep_time):
            if event & select.POLLIN or event & select.POLLPRI:
                ready.append(io)
            elif event & select.POLLHUP or event & select.POLLERR or event & select.POLLNVAL:
                sys.exit(1)
        return ready

    def no_buffer(self, fd):
        mfl = fcntl.fcntl(fd, fcntl.F_GETFL)
        mfl |= os.O_SYNC
        fcntl.fcntl(fd, fcntl.F_SETFL, mfl)

    def open_recv(self):
        """Open the fifo the daemon answers on, or end the process saying why.

        terminate() sets a flag and cleans up, it only exits when called a second time, so
        answering a failed open with it left loop() running with r_pipe None: read_on skips
        a None descriptor, so it polled stdin for ever, forwarded commands into the write
        fifo and read an answer from nowhere. There is no loop to run without this one.
        """
        try:
            self.r_pipe = os.open(self.recv, os.O_RDWR | os.O_NONBLOCK | os.O_EXCL)
        except OSError as exc:
            # stdout is the pipe to the daemon, so the report has to go to stderr.
            sys.stderr.write(f'could not open the named pipe {self.recv} ({exc})\n')
            sys.stderr.flush()
            self.terminate()
            sys.exit(1)

    def loop(self):
        self.open_recv()

        standard_in = sys.stdin.fileno()
        standard_out = sys.stdout.fileno()

        # Enable ACK for this CLI control process to ensure command responses are always received
        try:
            os.write(standard_out, b'enable-ack\n')
            # Read and discard the 'done' response to prevent it from interfering with user commands
            # Wait up to 1 second for the response
            poller = select.poll()
            poller.register(standard_in, select.POLLIN)
            if poller.poll(1000):
                # Read until we get a newline (the 'done' response)
                response = b''
                while b'\n' not in response:
                    chunk = os.read(standard_in, 1024)
                    if not chunk:
                        break
                    response += chunk
        except OSError as exc:
            # Without ack the daemon stops confirming the end of a command, so every cli
            # invocation from here on waits out its five second timeout and prints "no end of
            # command message received". That warning is the symptom; this line is the cause.
            # stdout is the pipe to the daemon, so the report has to go to stderr.
            sys.stderr.write(f'could not enable ack on the control pipe ({exc}), replies may not be seen\n')
            sys.stderr.flush()

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
        def fifo_reader(number):
            try:
                return os.read(self.r_pipe, number)
            except OSError as exc:
                if exc.errno in error.block:
                    return b''
                sys.exit(1)

        @monitor
        def fifo_writer(line):
            pipe, nb = None, 0
            try:
                pipe = os.open(self.send, os.O_WRONLY | os.O_NONBLOCK | os.O_EXCL)
                self.no_buffer(pipe)
            except OSError:
                time.sleep(0.05)
                return 0
            if pipe is not None:
                try:
                    nb = os.write(pipe, line)
                except OSError as exc:
                    # The pipe had a reader when we opened it and lost it before the write.
                    # Returning 0 makes the caller retry the same line, so silence here is a
                    # command which never arrives and a loop which never says why.
                    sys.stderr.write(f'cannot write {len(line)} bytes to {self.send}: {exc}\n')
                    sys.stderr.flush()
                # The bytes are written or lost by now, and the descriptor goes either way.
                with contextlib.suppress(OSError):
                    os.close(pipe)
            return nb

        read = {
            standard_in: std_reader,
            self.r_pipe: fifo_reader,
        }

        write = {
            standard_in: fifo_writer,
            self.r_pipe: std_writer,
        }

        backlog = {
            standard_in: Backlog(),
            self.r_pipe: Backlog(),
        }

        store = {
            standard_in: b'',
            self.r_pipe: b'',
        }

        def consume(source):
            if not backlog[source] and b'\n' not in store[source]:
                store[source] += read[source](1024)
                # a source which never sends a newline would otherwise grow store forever
                if len(store[source]) > MAX_COMMAND_SIZE and b'\n' not in store[source]:
                    sys.stderr.write('received a command larger than %d bytes - exiting\n' % MAX_COMMAND_SIZE)
                    sys.exit(1)
            else:
                backlog[source].append(read[source](1024))
                # assuming a route takes 80 chars, 100 Mb is over 1Millions routes
                # something is really wrong if it was not consummed
                if backlog[source].nbytes + len(store[source]) > MAX_BACKLOG_SIZE:
                    sys.stderr.write('using too much memory - exiting\n')
                    sys.exit(1)

        reading = [standard_in, self.r_pipe]

        while True:
            ready = self.read_on(reading)

            # command from user
            if self.r_pipe in ready:
                consume(self.r_pipe)
            if standard_in in ready:
                consume(standard_in)

            for source in reading:
                while b'\n' in store[source]:
                    line, _ = store[source].split(b'\n', 1)
                    # sys.stderr.write(str(line).replace('\n','\\n') + '\n')
                    # sys.stderr.flush()
                    sent = write[source](line + b'\n')
                    # sys.stderr.write('sent %d\n' % sent)
                    # sys.stderr.flush()
                    if sent:
                        store[source] = store[source][sent:]
                        continue
                    break
                if backlog[source]:
                    store[source] += backlog[source].popleft()

    def run(self):
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
    if not location:
        location = os.environ.get('exabgp_cli_pipe', '')
    if not location:
        argv_str = ' '.join(sys.argv)
        sys.stderr.write(f'usage {sys.executable} {argv_str}\n')
        sys.stderr.write("run with 'env exabgp_cli_pipe=<location>' if you are trying to mess with ExaBGP's internals")
        sys.stderr.flush()
        sys.exit(1)
    Control(location).run()


if __name__ == '__main__':
    main()
