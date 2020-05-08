#!/usr/bin/env python
# encoding: utf-8
"""
cli.py

Created by Thomas Mangin on 2014-12-22.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

import os
import sys
import time
import select
import signal
import errno

from exabgp.application.bgp import root_folder
from exabgp.application.bgp import named_pipe
from exabgp.application.bgp import get_envfile
from exabgp.application.bgp import get_env
from exabgp.application.control import check_fifo

from exabgp.reactor.network.error import error
from exabgp.reactor.api.response.answer import Answer

from exabgp.vendoring import docopt

errno_block = set(
    (
        errno.EINPROGRESS,
        errno.EALREADY,
        errno.EAGAIN,
        errno.EWOULDBLOCK,
        errno.EINTR,
        errno.EDEADLK,
        errno.EBUSY,
        errno.ENOBUFS,
        errno.ENOMEM,
    )
)

usage = """\
The BGP swiss army knife of networking

usage: exabgpcli [--root ROOT]
\t\t\t\t\t\t\t\t [--help|<command>...]
\t\t\t\t\t\t\t\t [--env ENV]

positional arguments:
\tcommand               valid exabgpcli command (see below)

optional arguments:
\t--env ENV,   -e ENV   environment configuration file
\t--help,      -h       exabgp manual page
\t--root ROOT, -f ROOT  root folder where etc,bin,sbin are located

commands:
\thelp                  show the commands known by ExaBGP
""".replace(
    '\t', '  '
)


class AnswerStream:
    done = '\n%s\n' % Answer.done
    error = '\n%s\n' % Answer.error
    shutdown = '\n%s\n' % Answer.error
    buffer_size = Answer.buffer_size + 2


def open_reader(recv):
    def open_timeout(signum, frame):
        sys.stderr.write('could not connect to read response from ExaBGP\n')
        sys.stderr.flush()
        sys.exit(1)

    signal.signal(signal.SIGALRM, open_timeout)
    signal.alarm(5)

    done = False
    while not done:
        try:
            reader = os.open(recv, os.O_RDONLY | os.O_NONBLOCK)
            done = True
        except IOError as exc:
            if exc.args[0] in errno_block:
                signal.signal(signal.SIGALRM, open_timeout)
                signal.alarm(5)
                continue
            sys.stdout.write('could not read answer from ExaBGP')
            sys.stdout.flush()
            sys.exit(1)
    signal.alarm(0)
    return reader


def open_writer(send):
    def write_timeout(signum, frame):
        sys.stderr.write('could not send command to ExaBGP (command timeout)')
        sys.stderr.flush()
        sys.exit(1)

    signal.signal(signal.SIGALRM, write_timeout)
    signal.alarm(5)

    try:
        writer = os.open(send, os.O_WRONLY)
    except OSError as exc:
        if exc.errno == errno.ENXIO:
            sys.stdout.write('ExaBGP is not running / using the configured named pipe')
            sys.stdout.flush()
            sys.exit(1)
        sys.stdout.write('could not communicate with ExaBGP')
        sys.stdout.flush()
        sys.exit(1)
    except IOError as exc:
        sys.stdout.write('could not communicate with ExaBGP')
        sys.stdout.flush()
        sys.exit(1)

    signal.alarm(0)
    return writer


def main():
    options = docopt.docopt(usage, help=False)
    if options['--env'] is None:
        options['--env'] = ''

    root = root_folder(options, ['/bin/exabgpcli', '/sbin/exabgpcli', '/lib/exabgp/application/cli.py'])
    prefix = '' if root == '/usr' else root
    etc = prefix + '/etc/exabgp'
    envfile = get_envfile(options, etc)
    env = get_env(envfile)
    pipename = env['api']['pipename']

    if options['--help']:
        sys.stdout.write(usage)
        sys.stdout.flush()
        sys.exit(0)

    if not options['<command>']:
        sys.stdout.write(usage)
        sys.stdout.flush()
        sys.exit(0)

    command = ' '.join(options['<command>'])

    pipes = named_pipe(root, pipename)
    if len(pipes) != 1:
        sys.stdout.write('could not find ExaBGP\'s named pipes (%s.in and %s.out) for the cli\n' % (pipename, pipename))
        sys.stdout.write('we scanned the following folders (the number is your PID):\n - ')
        sys.stdout.write('\n - '.join(pipes))
        sys.stdout.flush()
        sys.exit(1)

    send = pipes[0] + pipename + '.in'
    recv = pipes[0] + pipename + '.out'

    if not check_fifo(send):
        sys.stdout.write('could not find write named pipe to connect to ExaBGP')
        sys.stdout.flush()
        sys.exit(1)

    if not check_fifo(recv):
        sys.stdout.write('could not find read named pipe to connect to ExaBGP')
        sys.stdout.flush()
        sys.exit(1)

    reader = open_reader(recv)

    rbuffer = b''
    start = time.time()
    while True:
        try:
            while select.select([reader], [], [], 0) != ([], [], []):
                rbuffer += os.read(reader, 4096)
                rbuffer = rbuffer[-AnswerStream.buffer_size :]
        except IOError as exc:
            if exc.errno in error.block:
                continue
            sys.stdout.write('could not clear named pipe from potential previous command data (%s)' % str(exc))
            sys.stdout.flush()
            sys.exit(1)
        except OSError as exc:
            if exc.errno in error.block:
                continue
            sys.stdout.write('could not clear named pipe from potential previous command data (%s)' % str(exc))
            sys.stdout.write(exc)
            sys.stdout.flush()
            sys.exit(1)

        # we are not ack'ing the command and probably have read all there is
        if time.time() > start + 1.5:
            break

        # we read nothing, nothing to do
        if not rbuffer:
            break

        # we read some data but it is not ending by a new line (ie: not a command completion)
        if rbuffer[-1] != 10:  # \n
            continue
        if AnswerStream.done.endswith(rbuffer[-len(AnswerStream.done) :]):
            break
        if AnswerStream.error.endswith(rbuffer[-len(AnswerStream.error) :]):
            break
        if AnswerStream.shutdown.endswith(rbuffer[-len(AnswerStream.shutdown) :]):
            break

    renamed = ['']

    for pos, token in enumerate(command.split()):
        for nickname, name, match in (
            ('a', 'announce', lambda pos, pre: pos == 0 or pre.count('.') == 3 or pre.count(':') != 0),
            ('a', 'attributes', lambda pos, pre: pre[-1] == 'announce' or pre[-1] == 'withdraw'),
            ('c', 'configuration', lambda pos, pre: True),
            ('e', 'eor', lambda pos, pre: pre[-1] == 'announce'),
            ('e', 'extensive', lambda _, pre: 'show' in pre),
            ('f', 'flow', lambda pos, pre: pre[-1] == 'announce' or pre[-1] == 'withdraw'),
            ('f', 'flush', lambda pos, pre: pos == 0 or pre.count('.') == 3 or pre.count(':') != 0),
            ('h', 'help', lambda pos, pre: pos == 0),
            ('i', 'in', lambda pos, pre: pre[-1] == 'adj-rib'),
            ('n', 'neighbor', lambda pos, pre: pos == 0 or pre[-1] == 'show'),
            ('r', 'route', lambda pos, pre: pre == 'announce' or pre == 'withdraw'),
            ('rr', 'route-refresh', lambda _, pre: pre == 'announce'),
            ('s', 'show', lambda pos, pre: pos == 0),
            ('t', 'teardown', lambda pos, pre: pos == 0 or pre.count('.') == 3 or pre.count(':') != 0),
            ('s', 'summary', lambda pos, pre: pos != 0),
            ('v', 'vps', lambda pos, pre: pre[-1] == 'announce' or pre[-1] == 'withdraw'),
            ('o', 'operation', lambda pos, pre: pre[-1] == 'announce'),
            ('o', 'out', lambda pos, pre: pre[-1] == 'adj-rib'),
            ('a', 'adj-rib', lambda pos, pre: pre[-1] in ['clear', 'flush', 'show']),
            ('w', 'withdraw', lambda pos, pre: pos == 0 or pre.count('.') == 3 or pre.count(':') != 0),
            ('w', 'watchdog', lambda pos, pre: pre[-1] == 'announce' or pre[-1] == 'withdraw'),
            ('neighbour', 'neighbor', lambda pos, pre: True),
            ('neigbour', 'neighbor', lambda pos, pre: True),
            ('neigbor', 'neighbor', lambda pos, pre: True),
        ):
            if (token == nickname or name.startswith(token)) and match(pos, renamed):
                renamed.append(name)
                break
        else:
            renamed.append(token)

    sending = ' '.join(renamed).strip()

    # This does not change the behaviour for well formed command
    if sending != command:
        print('command: %s' % sending)

    writer = open_writer(send)
    try:
        os.write(writer, sending.encode('utf-8') + b'\n')
        os.close(writer)
    except IOError as exc:
        sys.stdout.write('could not send command to ExaBGP (%s)' % str(exc))
        sys.stdout.flush()
        sys.exit(1)
    except OSError as exc:
        sys.stdout.write('could not send command to ExaBGP (%s)' % str(exc))
        sys.stdout.flush()
        sys.exit(1)

    if command == 'reset':
        sys.exit(0)

    waited = 0.0
    buf = b''
    done = False
    done_time_diff = 0.5
    while not done:
        try:
            r, _, _ = select.select([reader], [], [], 0.01)
        except OSError as exc:
            if exc.errno in error.block:
                continue
            sys.stdout.write('could not get answer from ExaBGP (%s)' % str(exc))
            sys.stdout.flush()
            sys.exit(1)
        except IOError as exc:
            if exc.errno in error.block:
                continue
            sys.stdout.write('could not get answer from ExaBGP (%s)' % str(exc))
            sys.stdout.flush()
            sys.exit(1)

        if waited > 5.0:
            sys.stderr.write('\n')
            sys.stderr.write('warning: no end of command message received\n')
            sys.stderr.write(
                'warning: normal if exabgp.api.ack is set to false otherwise some data may get stuck on the pipe\n'
            )
            sys.stderr.write('warning: otherwise it may cause exabgp reactor to block\n')
            sys.exit(0)
        elif not r:
            waited += 0.01
            continue
        else:
            waited = 0.0

        try:
            raw = os.read(reader, 4096)
        except OSError as exc:
            if exc.errno in error.block:
                continue
            sys.stdout.write('could not read answer from ExaBGP (%s)' % str(exc))
            sys.stdout.flush()
            sys.exit(1)
        except IOError as exc:
            if exc.errno in error.block:
                continue
            sys.stdout.write('could not read answer from ExaBGP (%s)' % str(exc))
            sys.stdout.flush()
            sys.exit(1)

        buf += raw
        while b'\n' in buf:
            line, buf = buf.split(b'\n', 1)
            string = line.decode()
            if string == Answer.done:
                done = True
                break
            if string == Answer.shutdown:
                sys.stderr.write('ExaBGP is shutting down, command aborted\n')
                sys.stderr.flush()
                done = True
                break
            if string == Answer.error:
                done = True
                sys.stderr.write('ExaBGP returns an error (see ExaBGP\'s logs for more information)\n')
                sys.stderr.write('use help for a list of available commands\n')
                sys.stderr.flush()
                break
            sys.stdout.write('%s\n' % string)
            sys.stdout.flush()

        if not env.get('api').get('ack') and not raw.decode():
            this_moment = time.time()
            recv_epoch_time = os.path.getmtime(recv)
            time_diff = this_moment - recv_epoch_time
            if time_diff >= done_time_diff:
                done = True

    try:
        os.close(reader)
    except Exception:
        pass

    sys.exit(0)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass
