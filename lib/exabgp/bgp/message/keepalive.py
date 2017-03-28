# encoding: utf-8
"""
keepalive.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

from exabgp.bgp.message.message import Message
from exabgp.bgp.message.notification import Notify

from exabgp.reactor.api.options import hexstring

# =================================================================== KeepAlive
#


@Message.register
class KeepAlive (Message):
	ID = Message.CODE.KEEPALIVE
	TYPE = chr(Message.CODE.KEEPALIVE)

	def message (self,negotiated=None):
		return self._message(b'')

	def __str__ (self):
		return "KEEPALIVE"

	@classmethod
	def unpack_message (cls, data, negotiated):  # pylint: disable=W0613
		# This can not happen at decode time as we check the length of the KEEPALIVE message
		# But could happen when calling the function programmatically
		if data:
			raise Notify('Keepalive can not have any payload but contains %s', hexstring(data))
		return cls()
