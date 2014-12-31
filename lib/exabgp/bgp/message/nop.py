# encoding: utf-8
"""
nop.py

Created by Thomas Mangin on 2009-11-06.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

from exabgp.bgp.message import Message

class NOP (Message):
	ID = Message.ID.NOP
	TYPE = chr(Message.ID.NOP)

	def message (self):
		return self._message(self.data)

	def __str__ (self):
		return "NOP"

	@classmethod
	def unpack (cls):
		return NOP()

_NOP = NOP()
