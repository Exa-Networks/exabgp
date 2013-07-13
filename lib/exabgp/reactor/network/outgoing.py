from .connection import Connection
from .tcp import create,bind,connect,MD5,nagle,TTL,async
from .error import NetworkError,NotConnected

class Outgoing (Connection):
	def __init__ (self,peer,local,md5,ttl):
		Connection.__init__(self,peer.afi,peer.ip,local.ip)

		# really an assert which should be removed at some point
		if peer.afi != local.afi:
			raise NotConnected('The local IP and peer IP must be of the same family (both IPv4 or both IPv6)')

		# peer and local are type Inet
		self.logger.wire("Connection to %s" % self.peer)

		try:
			self.io = create(peer.afi)
			bind(self.io,local.ip,local.afi)
			connect(self.io,peer.ip,peer.afi,md5)
			async(self.io,peer.ip)
			nagle(self.io,peer.ip)
			TTL(self.io,peer.ip,ttl)
			MD5(self.io,peer.ip,peer.afi,md5)
		except NetworkError,e:
			self.close()
			raise NotConnected(str(e))
