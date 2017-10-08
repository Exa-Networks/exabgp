"""
control.py

Created by Thomas Mangin on 2015-01-13.
Copyright (c) 2015-2015 Exa Networks. All rights reserved.
"""

import os
import sys
import stat
import time
import signal
import select
import socket
import traceback

from exabgp.reactor.network.error import error


class Control (object):
	terminating = False

	def __init__ (self, location):
		self.send = location + '.out'
		self.recv = location + '.in'
		self.r_pipe = None

	def init (self):
		def _make_fifo (name):
			try:
				if not os.path.exists(name):
					os.mkfifo(name)
				elif not stat.S_ISFIFO(os.stat(name).st_mode):
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

		if not _make_fifo(self.recv):
			self.terminate()
			sys.exit(1)

		if not _make_fifo(self.send):
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
				raise e

		@monitor
		def std_writer (line):
			try:
				return os.write(standard_out,line)
			except OSError as exc:
				if exc.errno in error.block:
					return 0
				raise e

		@monitor
		def fifo_reader (number):
			try:
				return os.read(self.r_pipe,number)
			except OSError as exc:
				if exc.errno in error.block:
					return ''
				raise e

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
			standard_in: '',
			self.r_pipe: '',
		}

		def consume (source):
			store[source] += read[source](1024)

		reading = [standard_in, self.r_pipe]

		while True:
			try:
				ready,_,_ = select.select(reading,[],[],0.05)
			except select.error as e:
				if e.args[0] == 4:  # Interrupted system call
					raise KeyboardInterrupt()
				sys.exit(1)  # Unknow error, ending

			# we buffer first so the two ends are not blocking
			if not ready:
				for source in reading:
					if '\n' in store[source]:
						line,_ = store[source].split('\n',1)
						line = line + '\n'
						sent = write[source](line)
						if sent:
							store[source] = store[source][sent:]
							continue
				continue

			# command from user
			if self.r_pipe in ready:
				consume(self.r_pipe)
			if standard_in in ready:
				consume(standard_in)

	def run (self):
		if not self.init():
			return False
		try:
			result = self.loop()
			self.cleanup()
			return result
		except KeyboardInterrupt:
			self.cleanup()
		except Exception as exc:
			print(exc)
			print('')
			traceback.print_exc(file=sys.stdout)
			sys.stdout.flush()
			self.cleanup()
			sys.exit(1)


def main (location=None):
	if not location:
		location = dict(zip(range(len(sys.argv)),sys.argv)).get(1,'/var/run/exabgp.sock')
	Control(location).run()


if __name__ == '__main__':
	main()
