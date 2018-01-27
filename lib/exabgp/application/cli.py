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
import select
import signal
import errno

from exabgp.application.bgp import root_folder
from exabgp.application.bgp import named_pipe
from exabgp.application.bgp import get_envfile
from exabgp.application.bgp import get_env
from exabgp.application.control import check_fifo

from exabgp.reactor.network.error import error

from exabgp.vendoring import docopt

usage = """\
The BGP swiss army knife of networking

usage: exabgpcli [--root ROOT]
\t\t\t\t\t\t\t\t [--help|<command>...]

positional arguments:
\tcommand               valid exabgpcli command (see below)

optional arguments:
\t--help,      -h       exabgp manual page
\t--root ROOT, -f ROOT  root folder where etc,bin,sbin are located

commands:
\thelp                  show the commands known by ExaBGP
""".replace('\t','  ')


def main ():
	options = docopt.docopt(usage, help=False)
	options['--env'] = ''  # exabgp compatibility

	root = root_folder(options,['/bin/exabgpcli','/sbin/exabgpcli','/lib/exabgp/application/cli.py'])
	etc = root + '/etc/exabgp'
	envfile = get_envfile(options,etc)
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

	pipes = named_pipe(root)
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

	def write_timeout(signum, frame):
		sys.stderr.write('could not send command to ExaBGP')
		sys.stderr.flush()
		sys.exit(1)

	signal.signal(signal.SIGALRM, write_timeout)
	signal.alarm(2)

	try:
		writer = os.open(send, os.O_WRONLY | os.O_EXCL)
		os.write(writer,command.encode('utf-8') + b'\n')
		os.close(writer)
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

	if command == 'reset':
		sys.exit(0)

	def read_timeout(signum, frame):
		sys.stderr.write('could not read answer to ExaBGP')
		sys.stderr.flush()
		sys.exit(1)

	signal.signal(signal.SIGALRM, read_timeout)

	try:
		signal.alarm(5)
		reader = os.open(recv, os.O_RDONLY | os.O_EXCL)
		signal.alarm(0)

		buf = b''
		done = False
		while not done:
			try:
				raw = os.read(reader,4096)
				buf += raw
				while b'\n' in buf:
					line,buf = buf.split(b'\n',1)
					if line == b'done':
						done = True
						break
					if line == b'shutdown':
						sys.stderr.write('ExaBGP is shutting down, command aborted\n')
						sys.stderr.flush()
						done = True
						break
					if line == b'error':
						done = True
						sys.stderr.write('ExaBGP returns an error\n')
						sys.stderr.flush()
						break
					sys.stdout.write('%s\n' % line.decode())
					sys.stdout.flush()

				select.select([reader],[],[],0.01)
			except OSError as exc:
				if exc.errno in error.block:
					break
			except IOError as exc:
				if exc.errno in error.block:
					break
		os.close(reader)

		sys.exit(0)
	except IOError:
		sys.stdout.write('could not read answer from ExaBGP')
		sys.stdout.flush()
	except OSError:
		sys.stdout.write('could not read answer from ExaBGP')
		sys.stdout.flush()


if __name__ == '__main__':
	try:
		main()
	except KeyboardInterrupt:
		pass
