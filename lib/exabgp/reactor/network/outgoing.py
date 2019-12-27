import time

from exabgp.vendoring import six

from exabgp.protocol.family import AFI
from .connection import Connection
from .tcp import create,bind
from .tcp import connect
from .tcp import MD5
from .tcp import nagle
from .tcp import TTL
from .tcp import TTLv6
from .tcp import asynchronous
from .tcp import ready
from .error import NetworkError


class Outgoing (Connection):
	direction = 'outgoing'

	def __init__ (self, afi, peer, local, port=179,md5='',md5_base64=False, ttl=None):
		Connection.__init__(self,afi,peer,local)

		self.ttl = ttl
		self.afi = afi
		self.md5 = md5
		self.md5_base64 = md5_base64
		self.port = port

	def _setup (self):
		try:
			self.io = create(self.afi)
			MD5(self.io,self.peer,self.port,self.md5,self.md5_base64)
			if self.afi == AFI.ipv4:
				TTL(self.io, self.peer, self.ttl)
			elif self.afi == AFI.ipv6:
				TTLv6(self.io, self.peer, self.ttl)
			if self.local:
				bind(self.io,self.local,self.afi)
			asynchronous(self.io, self.peer)
			return True
		except NetworkError as exc:
			self.close()
			return False

	def _connect (self):
		try:
			connect(self.io,self.peer,self.port,self.afi,self.md5)
			return True
		except NetworkError as exc:
			return False

	def establish (self):
		last = time.time() - 2.0
		self._setup()

		while True:
			notify = (time.time() - last > 1.0)
			if notify:
				last = time.time()

			if notify:
				self.logger.debug('attempting connection to %s:%d' % (self.peer,self.port),self.session())

			if not self._connect():
				if notify:
					self.logger.debug('connection to %s:%d failed' % (self.peer,self.port),self.session())
				yield False
				continue

			connected = False
			for r,message in ready(self.io):
				if not r:
					yield False
					continue
				connected = True

			if connected:
				self.success()
				if not self.local:
					self.local = self.io.getsockname()[0]
				yield True
				return

			self._setup()

		# nagle(self.io,self.peer)
		# # Not working after connect() at least on FreeBSD TTL(self.io,self.peer,self.ttl)
		# yield True
