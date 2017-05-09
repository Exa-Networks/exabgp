# encoding: utf-8
"""
nop.py

Created by Thomas Mangin on 2009-11-06.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

from exabgp.util import character

from exabgp.bgp.message.message import Message

# ========================================================================= NOP
#


class NOP (Message):
	ID = Message.CODE.NOP
	TYPE = character(Message.CODE.NOP)

	def message (self,negotiated=None):
		raise RuntimeError('NOP messages can not be sent on the wire')

	def __str__ (self):
		return "NOP"

	@classmethod
	def unpack_message (cls, data, negotiated):  # pylint: disable=W0613
		return NOP()

_NOP = NOP()
