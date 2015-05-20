"""
control.py

Created by Thomas Mangin on 2015-01-13.
Copyright (c) 2015-2015 Exa Networks. All rights reserved.
"""

import os
import sys
import stat
import signal
import select
import socket
import traceback


class Control (object):
	def __init__ (self, location=None):
		self.location = location
		self.fifo_read = None
		self.fifo_write = None

	def delete (self):
		try:
			if os.path.exists(self.location):
				os.remove(self.location)
		except IOError:
			sys.stdout.write('error: could not remove current named pipe (%s)\n' % os.path.abspath(self.location))
			sys.stdout.flush()

	def cleanup (self):
		if self.fifo_read:
			try:
				self.fifo_read.close()
			except IOError:
				pass
		if self.fifo_write:
			try:
				self.fifo_write.close()
			except IOError:
				pass
		self.delete()

	# Can raise IOError, socket.error
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

			signal.signal(signal.SIGINT, self.delete)
			signal.signal(signal.SIGTERM, self.delete)
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

	def loop (self):
		report = ''

		self.fifo_read = open(self.location,'r')
		self.fifo_write = open(self.location,'w')

		read = {
			sys.stdin: sys.stdin.readline,
			self.fifo_read: self.fifo_read.readline,
		}

		write = {
			sys.stdin: self.fifo_write,
			self.fifo_read: sys.stdout,
		}

		store = {
			sys.stdin: '',
			self.fifo_read: '',
		}

		while True:
			ready,_,_ = select.select(read.keys(),[],[],1)
			if not ready:
				continue

			for source in ready:
				new = read[source]()
				data = store[source] + new

				if '\n' not in data:
					store[source] = data
					data = ''
					continue

				store[source] = ''
				write[source].write(data)
				write[source].flush()

		# This is only for the unittesting code
		return report

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
