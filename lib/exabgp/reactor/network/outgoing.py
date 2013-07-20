from .connection import Connection
from .tcp import create,bind,connect,MD5,nagle,TTL,async
from .error import NetworkError,NotConnected

class Outgoing (Connection):
	direction = 'outgoing'

	def __init__ (self,afi,peer,local,port=179,md5='',ttl=None):
		Connection.__init__(self,afi,peer,local)

		self.logger.wire("Connection to %s" % self.peer)

		try:
			self.io = create(afi)
			bind(self.io,local,afi)
			connect(self.io,peer,port,afi,md5)
			async(self.io,peer)
			nagle(self.io,peer)
			TTL(self.io,peer,ttl)
			MD5(self.io,peer,port,afi,md5)
		except NetworkError,e:
			self.close()
			raise NotConnected(str(e))
