# encoding: utf-8
"""
unknown.py

Created by Thomas Mangin on 2013-07-20.
Copyright (c) 2009-2013 Exa Networks. All rights reserved.
"""

from exabgp.bgp.message import Message

class Unknown (Message):
	# Make sure we have a value, which is not defined in any RFC !
	TYPE = chr(0xFF)

	def __init__ (self,data=''):
		self.factory(data)

	def factory (self,data):
		self.data = data
		return self

	def message (self):
		return self._message(self.data)

	def __str__ (self):
		return "UNKNOWN"
