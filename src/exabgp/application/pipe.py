"""pipe.py

Created by Thomas Mangin on <unset>.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import os
import sys
import fcntl
import stat
import time
import signal
import select
import traceback
from collections import deque

from exabgp.reactor.network.error import error

kb = 1024
mb = kb * 1024


def named_pipe(root: str, pipename: str = 'exabgp') -> list[str]:
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
        except OSError:
            continue
        os.environ['exabgp_cli_pipe'] = location
        return [location]
    return locations


def env(app: str, section: str, name: str, default: str) -> str:
    r = os.environ.get(f'{app}.{section}.{name}', None)
    if r is None:
        r = os.environ.get(f'{app}_{section}_{name}', None)
    if r is None:
        return default
    return r


def check_fifo(name: str) -> bool | None:
    try:
        if not stat.S_ISFIFO(os.stat(name).st_mode):
            sys.stdout.write(f'error: a file exist which is not a named pipe ({os.path.abspath(name)})\n')
            return False

        if not os.access(name, os.R_OK):
            sys.stdout.write(
                f'error: a named pipe exists and we can not read/write to it ({os.path.abspath(name)})\n',
            )
            return False
        return True
    except OSError:
        sys.stdout.write(f'error: could not create the named pipe {os.path.abspath(name)}\n')
        return False
    except OSError:
        sys.stdout.write(f'error: could not access/delete the named pipe {os.path.abspath(name)}\n')
        sys.stdout.flush()
        return None
    except OSError:
        sys.stdout.write(f'error: could not write on the named pipe {os.path.abspath(name)}\n')
        sys.stdout.flush()
        return None


class Control:
    terminating = False

    def __init__(self, location: str) -> None:
        self.send = location + env('exabgp', 'api', 'pipename', 'exabgp') + '.out'
        self.recv = location + env('exabgp', 'api', 'pipename', 'exabgp') + '.in'
        self.r_pipe: int | None = None

    def init(self) -> bool:
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

    def cleanup(self) -> None:
        def _close(pipe: int | None) -> None:
            if pipe:
                try:
                    os.close(pipe)
                except (OSError, TypeError):
                    pass

        _close(self.r_pipe)

    def terminate(self, ignore: object = None, me: object = None) -> None:
        # if the named pipe is open, and remove_fifo called
        # do not ignore a second signal
        if self.terminating:
            sys.exit(1)
        self.terminating = True

        self.cleanup()

    def read_on(self, reading: list[int | None]) -> list[int]:
        sleep_time = 1000

        poller = select.poll()
        for io in reading:
            if io is not None:
                poller.register(io, select.POLLIN | select.POLLPRI | select.POLLHUP | select.POLLNVAL | select.POLLERR)

        ready: list[int] = []
        for io, event in poller.poll(sleep_time):
            if event & select.POLLIN or event & select.POLLPRI:
                ready.append(io)
            elif event & select.POLLHUP or event & select.POLLERR or event & select.POLLNVAL:
                sys.exit(1)
        return ready

    def no_buffer(self, fd: int) -> None:
        mfl = fcntl.fcntl(fd, fcntl.F_GETFL)
        mfl |= os.O_SYNC
        fcntl.fcntl(fd, fcntl.F_SETFL, mfl)

    def loop(self) -> None:
        try:
            self.r_pipe = os.open(self.recv, os.O_RDWR | os.O_NONBLOCK | os.O_EXCL)
        except OSError:
            self.terminate()

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
        except OSError:
            # If we can't send the command or read the response, continue anyway
            pass

        def monitor(function):  # type: ignore[no-untyped-def]
            def wrapper(*args):  # type: ignore[no-untyped-def]
                r = function(*args)
                return r

            return wrapper

        @monitor
        def std_reader(number):  # type: ignore[no-untyped-def]
            try:
                return os.read(standard_in, number)
            except OSError as exc:
                if exc.errno in error.block:
                    return b''
                sys.exit(1)

        @monitor
        def std_writer(line):  # type: ignore[no-untyped-def]
            try:
                return os.write(standard_out, line)
            except OSError as exc:
                if exc.errno in error.block:
                    return 0
                sys.exit(1)

        @monitor
        def fifo_reader(number):  # type: ignore[no-untyped-def]
            if self.r_pipe is None:
                return b''
            try:
                return os.read(self.r_pipe, number)
            except OSError as exc:
                if exc.errno in error.block:
                    return b''
                sys.exit(1)

        @monitor
        def fifo_writer(line):  # type: ignore[no-untyped-def]
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
                except OSError:
                    pass
                try:
                    os.close(pipe)
                except OSError:
                    pass
            return nb

        read = {
            standard_in: std_reader,
            self.r_pipe: fifo_reader,
        }

        write = {
            standard_in: fifo_writer,
            self.r_pipe: std_writer,
        }

        backlog: dict[int | None, deque[bytes]] = {
            standard_in: deque(),
            self.r_pipe: deque(),
        }

        store = {
            standard_in: b'',
            self.r_pipe: b'',
        }

        def consume(source: int) -> None:
            if not backlog[source] and b'\n' not in store[source]:
                store[source] += read[source](1024)
            else:
                backlog[source].append(read[source](1024))
                # assuming a route takes 80 chars, 100 Mb is over 1Millions routes
                # something is really wrong if it was not consummed
                if len(backlog) > 100 * mb:
                    sys.stderr.write('using too much memory - exiting')
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

    def run(self) -> None:
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
