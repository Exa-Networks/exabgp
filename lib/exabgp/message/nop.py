# encoding: utf-8
"""
nop.py

Created by Thomas Mangin on 2009-11-06.
Copyright (c) 2009-2012 Exa Networks. All rights reserved.
"""

from exabgp.message import Message

class NOP (Message):
	TYPE = chr(0x00)

	def __init__ (self,data):
		self.data = data

	def message (self):
		return self._message(self.data)

