# encoding: utf-8
"""
keepalive.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

from exabgp.bgp.message.message import Message

# =================================================================== KeepAlive
#


@Message.register
class KeepAlive (Message):
	ID = Message.CODE.KEEPALIVE
	TYPE = chr(Message.CODE.KEEPALIVE)

	def message (self,negotiated=None):
		return self._message('')

	def __str__ (self):
		return "KEEPALIVE"

	@classmethod
	def unpack_message (cls, data, negotiated):  # pylint: disable=W0613
		# XXX: FIXME: raise Notify if data has something
		return cls()
