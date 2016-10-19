from exabgp.protocol.family import AFI
from .connection import Connection
from .tcp import create,bind
from .tcp import connect
from .tcp import MD5
from .tcp import nagle
from .tcp import TTL
from .tcp import TTLv6
from .tcp import async
from .tcp import ready
from .error import NetworkError


class Outgoing (Connection):
	direction = 'outgoing'

	def __init__ (self, afi, peer, local, port=179,md5='',ttl=None):
		Connection.__init__(self,afi,peer,local)

		self.logger.wire("Attempting connection to %s" % self.peer)

		self.peer = peer
		self.ttl = ttl
		self.afi = afi
		self.md5 = md5
		self.port = port

		try:
			self.io = create(afi)
			MD5(self.io,peer,port,md5)
			bind(self.io,local,afi)
			async(self.io,peer)
			if afi == AFI.ipv4:
				TTL(self.io,peer,ttl)
			elif afi == AFI.ipv6:
				TTLv6(self.io,peer,ttl)
			connect(self.io,peer,port,afi,md5)
			self.init = True
		except NetworkError,exc:
			self.init = False
			self.close()
			self.logger.wire("Connection failed, %s" % str(exc))

	def establish (self):
		if not self.init:
			yield False
			return

		try:
			generator = ready(self.io)
			while True:
				connected = generator.next()
				if not connected:
					yield False
					continue
				yield True
				return
		except StopIteration:
			# self.io MUST NOT be closed here, it is closed by the caller
			yield False
			return

		nagle(self.io,self.peer)
		TTL(self.io,self.peer,self.ttl)
		yield True
