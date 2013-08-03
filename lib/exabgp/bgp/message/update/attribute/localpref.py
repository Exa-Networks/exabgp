# encoding: utf-8
"""
attributes.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2013 Exa Networks. All rights reserved.
"""

from struct import unpack

from exabgp.bgp.message.update.attribute.id import AttributeID
from exabgp.bgp.message.update.attribute import Flag,Attribute

# =================================================================== Local Preference (5)

class LocalPreference (Attribute):
	ID = AttributeID.LOCAL_PREF
	FLAG = Flag.TRANSITIVE
	MULTIPLE = False

	def __init__ (self,localpref):
		self.localpref = self._attribute(localpref)
		self._str = str(unpack('!L',localpref)[0])

	def pack (self,asn4=None):
		return self.localpref

	def __len__ (self):
		return 4

	def __str__ (self):
		return self._str
