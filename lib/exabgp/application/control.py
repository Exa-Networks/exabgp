"""
control.py

Created by Thomas Mangin on 2015-01-13.
Copyright (c) 2015-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

import os
import sys
import stat
import time
import signal
import select
import socket
import traceback

from exabgp.util import str_ascii
from exabgp.reactor.network.error import error


def check_fifo (name):
	try:
		if not stat.S_ISFIFO(os.stat(name).st_mode):
			sys.stdout.write('error: a file exist which is not a named pipe (%s)\n' % os.path.abspath(name))
			return False

		if not os.access(name,os.R_OK):
			sys.stdout.write('error: a named pipe exists and we can not read/write to it (%s)\n' % os.path.abspath(name))
			return False
		return True
	except OSError:
		sys.stdout.write('error: could not create the named pipe %s\n' % os.path.abspath(name))
		return False
	except IOError:
		sys.stdout.write('error: could not access/delete the named pipe %s\n' % os.path.abspath(name))
		sys.stdout.flush()
	except socket.error:
		sys.stdout.write('error: could not write on the named pipe %s\n' % os.path.abspath(name))
		sys.stdout.flush()


class Control (object):
	terminating = False

	def __init__ (self, location):
		self.send = location + 'exabgp.out'
		self.recv = location + 'exabgp.in'
		self.r_pipe = None

	def init (self):
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

	def cleanup (self):
		def _close (pipe):
			if self.r_pipe:
				try:
					os.close(pipe)
				except (OSError,IOError,TypeError):
					pass

		_close(self.r_pipe)

	def terminate (self,ignore=None,me=None):
		# if the named pipe is open, and remove_fifo called
		# do not ignore a second signal
		if self.terminating:
			sys.exit(1)
		self.terminating = True

		self.cleanup()

		# def _remove_fifo (name):
		# 	# If we got two signal, time to stop trying nicely as we can not delete a file which is open
		# 	try:
		# 		if os.path.exists(name):
		# 			os.remove(name)
		# 	except IOError:
		# 		sys.stdout.write('error: could not remove current named pipe (%s)\n' % os.path.abspath(name))
		# 		sys.stdout.flush()

		# self._remove_fifo(self.recv)
		# self._remove_fifo(self.send)

	def loop (self):
		try:
			self.r_pipe = os.open(self.recv, os.O_RDONLY | os.O_NONBLOCK | os.O_EXCL)
		except OSError:
			self.terminate()

		standard_in = sys.stdin.fileno()
		standard_out = sys.stdout.fileno()

		def monitor (function):
			def wrapper (*args):
				# print >> sys.stderr, "%s(%s)" % (function.func_name,','.join([str(_).replace('\n','\\n') for _ in args]))
				r = function(*args)
				# print >> sys.stderr, "%s -> %s" % (function.func_name,str(r))
				return r
			return wrapper

		@monitor
		def std_reader (number):
			try:
				return os.read(standard_in,number)
			except OSError as exc:
				if exc.errno in error.block:
					return ''
				sys.exit(1)

		@monitor
		def std_writer (line):
			try:
				return os.write(standard_out,line)
			except OSError as exc:
				if exc.errno in error.block:
					return 0
				sys.exit(1)

		@monitor
		def fifo_reader (number):
			try:
				return os.read(self.r_pipe,number)
			except OSError as exc:
				if exc.errno in error.block:
					return ''
				sys.exit(1)

		@monitor
		def fifo_writer (line):
			pipe,nb = None,0
			try:
				pipe = os.open(self.send, os.O_WRONLY | os.O_NONBLOCK | os.O_EXCL)
			except OSError:
				time.sleep(0.05)
				return 0
			if pipe is not None:
				try:
					nb = os.write(pipe,line)
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

		store = {
			standard_in: b'',
			self.r_pipe: b'',
		}

		def consume (source):
			store[source] += read[source](1024)

		reading = [standard_in, self.r_pipe]

		while True:
			try:
				ready,_,_ = select.select(reading,[],[],1.0)
			except select.error as e:
				if e.args[0] in error.block:
					continue
				sys.exit(1)  # Unknow error, ending

			# command from user
			if self.r_pipe in ready:
				consume(self.r_pipe)
			if standard_in in ready:
				consume(standard_in)

			for source in reading:
				while b'\n' in store[source]:
					line,_ = store[source].split(b'\n',1)
					line = line + b'\n'
					sent = write[source](line)
					if sent:
						store[source] = store[source][sent:]
						continue
					break

	def run (self):
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


def main (location=''):
	if not location:
		location = os.environ.get('exabgp_cli_pipe','')
	if not location:
		sys.stderr.write("usage %s %s\n" % (sys.executable,' '.join(sys.argv)))
		sys.stderr.write("run with 'env exabgp_cli_pipe=<location>' if you are trying to mess with ExaBGP's intenals")
		sys.stderr.flush()
		sys.exit(1)
	Control(location).run()


if __name__ == '__main__':
	main()
