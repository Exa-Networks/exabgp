# encoding: utf-8
"""
attributes.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2013 Exa Networks. All rights reserved.
"""

from exabgp.bgp.message.update.attribute.id import AttributeID
from exabgp.bgp.message.update.attribute import Flag,Attribute

# =================================================================== Origin (1)

class Origin (Attribute):
	ID = AttributeID.ORIGIN
	FLAG = Flag.TRANSITIVE
	MULTIPLE = False

	IGP        = 0x00
	EGP        = 0x01
	INCOMPLETE = 0x02

	def __init__ (self,origin):
		self.origin = origin

	def pack (self,asn4=None):
		return self._attribute(chr(self.origin))

	def __len__ (self):
		return len(self.pack())

	def __str__ (self):
		if self.origin == 0x00: return 'igp'
		if self.origin == 0x01: return 'egp'
		if self.origin == 0x02: return 'incomplete'
		return 'invalid'
