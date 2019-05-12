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
""".replace('\t','  ')


class AnswerStream:
	done = '\n%s\n' % Answer.done
	error = '\n%s\n' % Answer.error
	shutdown = '\n%s\n' % Answer.error
	buffer_size = Answer.buffer_size + 2

def main ():
	options = docopt.docopt(usage, help=False)
	if options['--env'] is None:
		options['--env'] = ''

	root = root_folder(options,['/bin/exabgpcli','/sbin/exabgpcli','/lib/exabgp/application/cli.py'])
	prefix = '' if root == '/usr' else root
	etc = prefix + '/etc/exabgp'
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

	def write_timeout(signum, frame):
		sys.stderr.write('could not send command to ExaBGP')
		sys.stderr.flush()
		sys.exit(1)

	buffer = ''
	start = time.time()
	try:
		reader = os.open(recv, os.O_RDONLY | os.O_EXCL | os.O_NONBLOCK)
		while True:
			while select.select([reader], [], [], 0) != ([], [], []):
				buffer += os.read(reader,4096)
				buffer = buffer[-AnswerStream.buffer_size:]
			# we read nothing, nothing to do
			if not buffer:
				break
			# we read some data but it is not ending by a new line (ie: not a command completion)
			if buffer[-1] != '\n':
				continue
			if AnswerStream.done.endswith(buffer[-len(AnswerStream.done):]):
				break
			if AnswerStream.error.endswith(buffer[-len(AnswerStream.error):]):
				break
			if AnswerStream.shutdown.endswith(buffer[-len(AnswerStream.shutdown):]):
				break
			# we are not ack'ing the command and probably have read all there is
			if time.time() > start + 1.5:
				break

	except Exception as exc:
		sys.stdout.write('could not clear named pipe from potential previous command data')
		sys.stdout.write(exc)
		sys.stdout.flush()

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

	def open_timeout(signum, frame):
		sys.stderr.write('could not open connection to ExaBGP')
		sys.stderr.flush()
		sys.exit(1)

	signal.signal(signal.SIGALRM, open_timeout)
	waited = 0.0

	try:
		signal.alarm(5)
		reader = os.open(recv, os.O_RDONLY | os.O_EXCL)
		signal.alarm(0)

		buf = b''
		done = False
		while not done:
			r,_,_ = select.select([reader], [], [], 0.01)
			if waited > 5.0:
				sys.stderr.write('\n')
				sys.stderr.write('warning: no end of command message received\n')
				sys.stderr.write('warning: normal if exabgp.api.ack is set to false otherwise some data may get stuck on the pipe\n')
				sys.stderr.write('warning: otherwise it may cause exabgp reactor to block\n')
				sys.exit(0)
			elif not r:
				waited += 0.01
				continue
			else:
				waited = 0.0
			try:
				raw = os.read(reader, 4096)
				buf += raw
				while b'\n' in buf:
					line,buf = buf.split(b'\n',1)
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
