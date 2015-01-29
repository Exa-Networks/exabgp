# encoding: utf-8
"""
attributes.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

from exabgp.bgp.message.update.attribute.attribute import Attribute


# =================================================================== Origin (1)

class Origin (Attribute):
	ID = Attribute.CODE.ORIGIN
	FLAG = Attribute.Flag.TRANSITIVE
	CACHING = True

	IGP        = 0x00
	EGP        = 0x01
	INCOMPLETE = 0x02

	__slots__ = ['origin','packed']

	def __init__ (self, origin, packed=None):
		self.origin = origin
		self.packed = self._attribute(packed if packed else chr(origin))

	def pack (self, negotiated=None):
		return self.packed

	def __len__ (self):
		return len(self.packed)

	def __str__ (self):
		if self.origin == 0x00:
			return 'igp'
		if self.origin == 0x01:
			return 'egp'
		if self.origin == 0x02:
			return 'incomplete'
		return 'invalid'

	def __cmp__ (self, other):
		if not isinstance(other,self.__class__):
			return -1
		if self.origin != other.origin:
			return -1
		return 0

	@classmethod
	def unpack (cls, data, negotiated):
		return cls(ord(data),data)

	@classmethod
	def setCache (cls):
		# there can only be three, build them now
		IGP = Origin(Origin.IGP)
		EGP = Origin(Origin.EGP)
		INC = Origin(Origin.INCOMPLETE)

		cls.cache[Attribute.CODE.ORIGIN][IGP.pack()] = IGP
		cls.cache[Attribute.CODE.ORIGIN][EGP.pack()] = EGP
		cls.cache[Attribute.CODE.ORIGIN][INC.pack()] = INC

Origin.setCache()
