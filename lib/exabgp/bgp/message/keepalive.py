# encoding: utf-8
"""
keepalive.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

from exabgp.bgp.message import Message

# =================================================================== KeepAlive

class KeepAlive (Message):
	ID = Message.ID.KEEPALIVE
	TYPE = chr(Message.ID.KEEPALIVE)

	def message (self):
		return self._message('')

	def __str__ (self):
		return "KEEPALIVE"

	@classmethod
	def unpack_message (cls,data,negotiated):
		# XXX: FIXME: raise Notify if data has something
		return cls()

KeepAlive.register_message()
