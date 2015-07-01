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

@Attribute.register()
class LocalPreference (Attribute):
	ID = Attribute.CODE.LOCAL_PREF
	FLAG = Attribute.Flag.TRANSITIVE
	CACHING = True

	__slots__ = ['localpref','_packed']

	def __init__ (self, localpref, packed=None):
		self.localpref = localpref
		self._packed = self._attribute(packed if packed is not None else pack('!L',localpref))

	def __eq__ (self, other):
		return \
			self.ID == other.ID and \
			self.FLAG == other.FLAG and \
			self.localpref == other.localpref

	def __ne__ (self, other):
		return not self.__eq__(other)

	def pack (self, negotiated=None):
		return self._packed

	def __len__ (self):
		return 4

	def __repr__ (self):
		return str(self.localpref)

	@classmethod
	def unpack (cls, data, negotiated):
		return cls(unpack('!L',data)[0],data)
