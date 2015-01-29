# encoding: utf-8
"""
generic.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

from struct import pack
from exabgp.bgp.message.update.attribute.attribute import Attribute


# ============================================================= GenericAttribute
#

class GenericAttribute (Attribute):
	__slots__ = ['ID','FLAG','data','index']

	def __init__ (self, code, flag, data):
		self.ID = code
		self.FLAG = flag
		self.data = data
		self.index = ''

	def pack (self, negotiated=None):
		flag = self.FLAG
		length = len(self.data)
		if length > 0xFF:
			flag |= Attribute.Flag.EXTENDED_LENGTH
		if flag & Attribute.Flag.EXTENDED_LENGTH:
			len_value = pack('!H',length)
		else:
			len_value = chr(length)
		return "%s%s%s%s" % (chr(flag),chr(self.ID),len_value,self.data)

	def __len__ (self):
		return len(self.data)

	def __str__ (self):
		return '0x' + ''.join('%02x' % ord(_) for _ in self.data)

	@classmethod
	def unpack (cls, code, flag, data):
		return cls(code,flag,data)
