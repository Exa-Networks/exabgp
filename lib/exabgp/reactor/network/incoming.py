from exabgp.util.errstr import errstr

from .connection import Connection
from .tcp import nagle,async
from .error import NetworkError,NotConnected

from exabgp.bgp.message.notification import Notify

class Incoming (Connection):
	direction = 'incoming'

	def __init__ (self,afi,peer,local,io):
		Connection.__init__(self,afi,peer,local)

		self.logger.wire("Connection from %s" % self.peer)

		try:
			self.io = io
			async(self.io,peer)
			nagle(self.io,peer)
		except NetworkError,e:
			self.close()
			raise NotConnected(errstr(e))

	def notification (self,code,subcode,message):
		try:
			notification = Notify(code,subcode,message).message()
			for boolean in self.writer(notification):
				yield False
			self.logger.message(self.me('>> NOTIFICATION (%d,%d,"%s")' % (notification.code,notification.subcode,notification.data)),'error')
			yield True
		except NetworkError:
			pass  # This is only be used when closing session due to unconfigured peers - so issues do not matter
