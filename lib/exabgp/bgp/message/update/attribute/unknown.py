# encoding: utf-8
"""
unknown.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2013 Exa Networks. All rights reserved.
"""

from struct import unpack

from exabgp.bgp.message.update.attribute import Attribute
from exabgp.bgp.message.update.attribute.id import AttributeID as AID

# =================================================================== MED (4)

class Unknown (Attribute):
	MULTIPLE = False

	def __init__ (self,code,flag,data):
		self.ID = code
		self.FLAG = flag
		self.data = data

	def pack (self):
		return self._attribute(self.data)

	def __len__ (self):
		return len(self.data)

	def __str__ (self):
		if self.ID in AID.INTEGER:
			return str(unpack('!L',self.data)[0])
		if self.ID in AID.INET:
			return '.'.join(str(ord(_)) for _ in self.data)
		return '0x' + ''.join('%02x' % ord(_) for _ in self.data)
