# encoding: utf-8
"""
nop.py

Created by Thomas Mangin on 2009-11-06.
Copyright (c) 2009-2013 Exa Networks. All rights reserved.
"""

from exabgp.bgp.message import Message

class NOP (Message):
	TYPE = chr(Message.Type.NOP)

	def message (self):
		return Message.message(self,self.data)

	def __str__ (self):
		return "NOP"

def NOPFactory (self):
	return NOP()
