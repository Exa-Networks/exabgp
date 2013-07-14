from .connection import Connection
from .tcp import nagle,async
from .error import NetworkError,NotConnected

class Incoming (Connection):
	def __init__ (self,afi,peer,local,io):
		Connection.__init__(self,afi,peer,local)

		self.logger.wire("Connection from %s" % self.peer)

		try:
			self.io = io
			async(self.io,peer)
			nagle(self.io,peer)
		except NetworkError:
			self.close()
			raise NotConnected(str(e))
