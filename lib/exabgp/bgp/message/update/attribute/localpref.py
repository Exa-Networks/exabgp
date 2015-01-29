# encoding: utf-8
"""
attributes.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

from struct import pack
from struct import unpack

from exabgp.bgp.message.update.attribute.attribute import Attribute


# ========================================================= Local Preference (5)
#

class LocalPreference (Attribute):
	ID = Attribute.CODE.LOCAL_PREF
	FLAG = Attribute.Flag.TRANSITIVE
	CACHING = True

	__slots__ = ['localpref','packed']

	def __init__ (self, localpref, packed=None):
		self.localpref = localpref
		self.packed = self._attribute(packed if packed is not None else pack('!L',localpref))

	def pack (self, negotiated=None):
		return self.packed

	def __len__ (self):
		return 4

	def __str__ (self):
		return str(self.localpref)

	def __cmp__ (self, other):
		if not isinstance(other,self.__class__):
			return -1
		if self.localpref != other.localpref:
			return -1
		return 0

	@classmethod
	def unpack (cls, data, negotiated):
		return cls(unpack('!L',data)[0],data)
