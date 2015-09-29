from .connection import Connection
from .tcp import create,bind
from .tcp import connect
from .tcp import MD5
from .tcp import nagle
from .tcp import TTL
from .tcp import async
from .tcp import ready
from .error import NetworkError


class Outgoing (Connection):
	direction = 'outgoing'

	def __init__ (self, afi, peer, local, port=179,md5='',ttl=None):
		Connection.__init__(self,afi,peer,local)

		self.logger.wire("attempting connection to %s:%d" % (self.peer,port))

		self.peer = peer
		self.ttl = ttl
		self.afi = afi
		self.md5 = md5
		self.port = port

		try:
			self.io = create(afi)
			MD5(self.io,peer,port,md5)
			TTL(self.io, peer, self.ttl)
			bind(self.io,local,afi)
			async(self.io,peer)
			connect(self.io,peer,port,afi,md5)
			self.init = True
		except NetworkError,exc:
			self.init = False
			self.close()
			self.logger.wire("connection to %s:%d failed, %s" % (self.peer,port,str(exc)))

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
		# Not working after connect() at least on FreeBSD TTL(self.io,self.peer,self.ttl)
		yield True
