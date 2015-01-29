# encoding: utf-8
"""
med.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

from struct import pack
from struct import unpack

from exabgp.bgp.message.update.attribute.attribute import Attribute


# ====================================================================== MED (4)
#

class MED (Attribute):
	ID = Attribute.CODE.MED
	FLAG = Attribute.Flag.OPTIONAL
	CACHING = True

	__slots__ = ['med','packed']

	def __init__ (self, med, packed=None):
		self.med = med
		self.packed = self._attribute(packed if packed is not None else pack('!L',med))

	def pack (self, negotiated=None):
		return self.packed

	def __len__ (self):
		return 4

	def __str__ (self):
		return str(self.med)

	def __cmp__ (self, other):
		if not isinstance(other,self.__class__):
			return -1
		if self.med != other.med:
			return -1
		return 0

	def __hash__ (self):
		return hash(self.med)

	@classmethod
	def unpack (cls, data, negotiated):
		return cls(unpack('!L',data)[0])
