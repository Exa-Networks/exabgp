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

	def __init__ (self, location=None):
		self.location = location
		self.r_pipe = None
		self.w_pipe = None

	def init (self):
		if not self.location:
			return False

		try:
			if not os.path.exists(self.location):
				os.mkfifo(self.location)
			elif not stat.S_ISFIFO(os.stat(self.location).st_mode):
				sys.stdout.write('error: a file exist which is not a named pipe (%s)\n' % os.path.abspath(self.location))
				return False

			if not os.access(self.location,os.R_OK | os.W_OK):
				sys.stdout.write('error: a named pipe exists and we can not read/write to it (%s)\n' % os.path.abspath(self.location))
				return False

			signal.signal(signal.SIGINT, self.terminate)
			signal.signal(signal.SIGTERM, self.terminate)
			return True
		except OSError:
			sys.stdout.write('error: could not create the named pipe %s\n' % os.path.abspath(self.location))
			return False
		except IOError:
			sys.stdout.write('error: could not access/delete the named pipe %s\n' % os.path.abspath(self.location))
			sys.stdout.flush()
		except socket.error:
			sys.stdout.write('error: could not write on the named pipe %s\n' % os.path.abspath(self.location))
			sys.stdout.flush()

	def remove_fifo (self):
		# If we got two signal, time to stop trying nicely as we can not delete a file which is open
		try:
			if os.path.exists(self.location):
				os.remove(self.location)
		except IOError:
			sys.stdout.write('error: could not remove current named pipe (%s)\n' % os.path.abspath(self.location))
			sys.stdout.flush()

	def cleanup (self):
		if self.r_pipe:
			try:
				os.close(self.r_pipe)
			except (OSError,IOError):
				pass
		if self.w_pipe:
			try:
				os.close(self.w_pipe)
			except (OSError,IOError):
				pass

	def terminate (self,ignore=None,me=None):
		# if the named pipe is open, and remove_fifo called
		# do not ignore a second signal
		if self.terminating:
			sys.exit(1)
		self.terminating = True

		self.cleanup()
		# self.remove_fifo()

	def loop (self):
		self.r_pipe = os.open(self.location, os.O_RDONLY | os.O_NONBLOCK | os.O_EXCL)
		self.w_pipe = os.open(self.location, os.O_WRONLY | os.O_NONBLOCK | os.O_EXCL)

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
			except OSError as e:
				if e.errno in error.block:
					return ''
				raise e

		@monitor
		def std_writer (line):
			try:
				return os.write(standard_out,line)
			except OSError as e:
				if e.errno in error.block:
					return 0
				raise e

		@monitor
		def fifo_reader (number):
			try:
				return os.read(self.r_pipe,number)
			except OSError as e:
				if e.errno in error.block:
					return ''
				raise e

		@monitor
		def fifo_writer (line):
			try:
				return os.write(self.w_pipe,line)
			except OSError as e:
				if e.errno in error.block:
					return 0
				raise e

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

		def have_data ():
			return '\n' in ''.join(store.values())

		def handle (source):
			data = store[source]
			while '\n' not in data:
				data = read[source](1024)

			while '\n' in data:
				line,data = data.split('\n',1)
				while line:
					l = write[source](line + '\n')
					if not l:
						time.sleep(0.05)
					line = line[l:]

			store[source] = data

		reading = [standard_in, self.r_pipe]
		last = None

		while True:
			try:
				ready,_,_ = select.select(reading,[],[],0.05)
			except select.error,e:
				if e.args[0] == 4:  # Interrupted system call
					raise KeyboardInterrupt()
			if not ready and not have_data():
				if last and time.time() - last > 10:
					last = None
					reading = [standard_in, self.r_pipe]
					store = {
						standard_in: '',
						self.r_pipe: '',
					}
				continue

			# command from user
			if self.r_pipe in ready or '\n' in store[self.r_pipe]:
				last = time.time()
				handle(self.r_pipe)
				# wait for the reply from the server, do not consume the data we produce
				reading = [standard_in]
			if standard_in in ready or '\n' in store[standard_in]:
				last = time.time()
				handle(standard_in)

	def run (self):
		if not self.init():
			return False
		try:
			result = self.loop()
			self.cleanup()
			return result
		except KeyboardInterrupt:
			self.cleanup()
		except Exception, exc:
			print exc
			print ''
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
