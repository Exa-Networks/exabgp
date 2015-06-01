from exabgp.util.errstr import errstr

from .connection import Connection
from .tcp import nagle
from .tcp import async
from .error import NetworkError
from .error import NotConnected

from exabgp.bgp.message import Notify


class Incoming (Connection):
	direction = 'incoming'

	def __init__ (self, afi, peer, local, io):
		Connection.__init__(self,afi,peer,local)

		self.logger.wire("Connection from %s" % self.peer)

		try:
			self.io = io
			async(self.io,peer)
			nagle(self.io,peer)
		except NetworkError,exc:
			self.close()
			raise NotConnected(errstr(exc))

	# XXX: FIXME: is that code ever called ?
	def notification (self, code, subcode, message):
		try:
			notification = Notify(code,subcode,message).message()
			for boolean in self.writer(notification):
				yield False
			# self.logger.message(self.me('>> NOTIFICATION (%d,%d,"%s")' % (notification.code,notification.subcode,notification.data)),'error')
			yield True
		except NetworkError:
			pass  # This is only be used when closing session due to unconfigured peers - so issues do not matter
