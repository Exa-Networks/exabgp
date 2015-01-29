"""
control.py

Created by Thomas Mangin on 2015-01-13.
Copyright (c) 2015-2015 Exa Networks. All rights reserved.
"""

import os
import sys
import select
import socket
import traceback


class Control (object):
	def __init__ (self, location=None,production=True):
		from exabgp.configuration.environment import environment
		self.location = location or environment.settings().api.socket

		self.unix = None
		self.sock = None
		self._production = production

	def __del__ (self):
		if self.sock:
			self.sock.close()
		if self.unix:
			self.unix.close()

		self.cleanup()

	# Can raise IOError
	def cleanup (self):
		if os.path.exists(self.location):
			os.remove(self.location)

	# Can raise IOError, socket.error
	def init (self):
		if not self.location:
			return False

		if not self.unix:
			try:
				# Can raise IOError
				self.cleanup()

				self.unix = socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
				# Can raise socket.error
				self.unix.bind(self.location)
				self.unix.listen(1)
				return True
			except IOError:
				print >> sys.stderr, 'could not access/delete socket file', self.location
			except socket.error:
				print >> sys.stderr, 'could not write socket file', self.location

			return False

	def write_standard (self, data):
		if not self._production:
			data = ''
		sys.stdout.write(data+'\n')
		sys.stdout.flush()

	def write_socket (self, data):
		self.sock.sendall(data)  # pylint: disable=E1101

	def read_socket (self, number):
		return self.sock.recv(number)  # pylint: disable=E1101

	def read_stdin (self, _):
		return sys.stdin.readline()

	def loop (self):
		report = ''

		while True:
			self.sock,_ = self.unix.accept()

			read = {
				sys.stdin: self.read_stdin,
				self.sock: self.read_socket,
			}

			write = {
				sys.stdin: self.write_socket,
				self.sock: self.write_standard,
			}

			store = {
				sys.stdin: '',
				self.sock: '',
			}

			looping = True
			while looping:
				ready,_,_ = select.select(read.keys(),[],[],1)
				if not ready:
					continue

				for fd in ready:
					r,_,_ = select.select([fd,],[],[],0)

					if r:
						new = read[fd](10240)
						if not new:
							looping = False
							break

						data = store[fd] + new

						while True:
							if '\n' not in data:
								store[fd] = data
								data = ''
								break
							report,data = data.split('\n',1)
							write[fd](report)

				if not self._production:
					return report

		# This is only for the unittesting code
		return report

	def run (self):
		try:
			if not self.init():
				return False
			return self.loop()
		except KeyboardInterrupt:
			self.cleanup()
		except Exception,exc:
			print >> sys.stderr, exc
			print >> sys.stderr,''
			traceback.print_exc(file=sys.stderr)
			sys.stderr.flush()
			self.cleanup()
			sys.exit(1)

if __name__ == '__main__':
	LOCATION = dict(zip(range(len(sys.argv)),sys.argv)).get(1,'/var/run/exabgp.sock')
	Control(LOCATION).run()
