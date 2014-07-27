# encoding: utf-8
"""
unknown.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2013 Exa Networks. All rights reserved.
"""

from exabgp.bgp.message.update.attribute.attribute import Attribute
from exabgp.bgp.message.update.attribute.flag import Flag

# ============================================================= UnknownAttribute
#

class UnknownAttribute (Attribute):
	MULTIPLE = False

	__slots__ = ['ID','FLAG','data','index']

	def __init__ (self,code,flag,data):
		self.ID = code
		self.FLAG = flag | Flag.PARTIAL
		self.data = data
		self.index = ''

	def pack (self,negotiated=None):
		return self._attribute(self.data)

	def __len__ (self):
		return len(self.data)

	def __str__ (self):
		return '0x' + ''.join('%02x' % ord(_) for _ in self.data)

	@classmethod
	def unpack (cls,code,flag,data):
		return cls(code,flag,data)
