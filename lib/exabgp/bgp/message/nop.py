# encoding: utf-8
"""
nop.py

Created by Thomas Mangin on 2009-11-06.
Copyright (c) 2009-2013 Exa Networks. All rights reserved.
"""

from exabgp.bgp.message import Message

class NOP (Message):
	TYPE = chr(0x00)

	def __init__ (self,data=''):
		self.factory(data)

	def factory (self,data):
		self.data = data
		return self

	def message (self):
		return self._message(self.data)

	def __str__ (self):
		return "NOP"
