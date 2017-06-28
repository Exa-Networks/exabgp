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

usage: exabgpcli [--root ROOT] [--env ENV] [--test]
\t\t\t\t\t\t\t\t [--help|<command>...]

positional arguments:
\tcommand               valid exabgpcli command (see below)

optional arguments:
\t--help,      -h       exabgp manual page
\t--root ROOT, -f ROOT  root folder where etc,bin,sbin are located
\t--env ENV,   -e ENV   environment configuration file

debugging:
\t--test,      -t       perform a configuration validity check only

commands:
\tversion               show the version of exabgp running
\tneighbors             show the configured neighbors
\tneigbor <ip>          show details for one neighbor
""".replace('\t','  ')


def main ():
	options = docopt.docopt(usage, help=False)

	root = root_folder(options,['/bin/exabgpcli','/sbin/exabgpcli','/lib/exabgp/application/cli.py'])
	etc = root + '/etc/exabgp'
	envfile = get_envfile(options,etc)
	env = get_env(envfile)

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
		sys.stdout.write('Could not find ExaBGP\'s named pipes (exabgp.in and exabgp.out) for the cli in any of ' + ', '.join(pipes))
		sys.stdout.flush()
		sys.exit(1)

	send = pipes[0] + 'exabgp.in'
	recv = pipes[0] + 'exabgp.out'

	if not check_fifo(send):
		sys.stdout.write('could not find write named pipe to connect to ExaBGP')
		sys.stdout.flush()
		sys.exit(1)

	if not check_fifo(recv):
		sys.stdout.write('could not find read named pipe to connect to ExaBGP')
		sys.stdout.flush()
		sys.exit(1)

	try:
		writer = os.open(send, os.O_WRONLY | os.O_NONBLOCK | os.O_EXCL)
		os.write(writer,command + '\n')
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

	try:
		reader = os.open(recv, os.O_RDONLY | os.O_NONBLOCK | os.O_EXCL)
		buf = ''
		done = False
		while not done:
			try:
				time.sleep(0.1)
				raw = os.read(reader,4096)
				buf += raw
				if buf == 'done' or buf == 'error':
					break
				raw = ''
				while '\n' in buf:
					line,buf = buf.split('\n',1)
					if line == 'done':
						sys.stdout.write('command sent\n')
						done = True
						break
					if line == 'error':
						done = True
						sys.stdout.write('ExaBGP returns an error\n')
						break
					sys.stdout.write('%s\n' % line)
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
