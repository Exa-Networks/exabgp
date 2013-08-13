# encoding: utf-8
"""
unknown.py

Created by Thomas Mangin on 2013-07-20.
Copyright (c) 2009-2013 Exa Networks. All rights reserved.
"""

from exabgp.bgp.message import Message

class UnknownMessage (Message):
	# Make sure we have a value, which is not defined in any RFC !

	def __init__ (self,code,data=''):
		self.TYPE = code
		self.data = data

	def message (self):
		return Message.message(self,self.data)

	def __str__ (self):
		return "UNKNOWN"

def UnknownMessageFactory (data):
	return UnknownMessage(data)
