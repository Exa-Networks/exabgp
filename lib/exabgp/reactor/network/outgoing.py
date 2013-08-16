from .connection import Connection
from .tcp import create,bind,connect,MD5,nagle,TTL,async,ready
from .error import NetworkError

class Outgoing (Connection):
	direction = 'outgoing'

	def __init__ (self,afi,peer,local,port=179,md5='',ttl=None):
		Connection.__init__(self,afi,peer,local)

		self.logger.wire("Connection to %s" % self.peer)

		self.peer = peer
		self.ttl = ttl
		self.afi = afi
		self.md5 = md5
		self.port = port

		try:
			self.io = create(afi)
			bind(self.io,local,afi)
			async(self.io,peer)
			connect(self.io,peer,port,afi,md5)
			self.init = True
		except NetworkError:
			self.init = False
			self.close()

	def connected (self):
		if not self.init:
			yield False
			return

		connected = False
		try:
			generator = ready(self.io)
			while True:
				connected = generator.next()
				if connected is True:
					break
				yield False
		finally:
			if connected is not True:
				yield False

		nagle(self.io,self.peer)
		TTL(self.io,self.peer,self.ttl)
		MD5(self.io,self.peer,self.port,self.afi,self.md5)
		yield True
