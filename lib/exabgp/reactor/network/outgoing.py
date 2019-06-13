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

		self.logger.debug('attempting connection to %s:%d' % (self.peer,port),self.session())

		self.ttl = ttl
		self.afi = afi
		self.md5 = md5
		self.port = port

		try:
			self.io = create(afi)
			MD5(self.io,self.peer,port,md5,md5_base64)
			if afi == AFI.ipv4:
				TTL(self.io, self.peer, self.ttl)
			elif afi == AFI.ipv6:
				TTLv6(self.io, self.peer, self.ttl)
			if local:
				bind(self.io,self.local,afi)
			asynchronous(self.io, self.peer)
			connect(self.io,self.peer,port,afi,md5)
			if not self.local:
				self.local = self.io.getsockname()[0]
			self.success()
			self.init = True
		except NetworkError as exc:
			self.init = False
			self.close()
			self.logger.debug('connection to %s:%d failed, %s' % (self.peer,port,str(exc)),self.session())

	def establish (self):
		if not self.init:
			yield False
			return

		generator = ready(self.io)
		for connected in generator:
			if not connected:
				yield False
				continue
			yield True
		yield False
		# self.io MUST NOT be closed here, it is closed by the caller

		# nagle(self.io,self.peer)
		# # Not working after connect() at least on FreeBSD TTL(self.io,self.peer,self.ttl)
		# yield True
