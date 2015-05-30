# encoding: utf-8
"""
nexthop.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

from exabgp.protocol.ip import IP
from exabgp.protocol.ip import NoNextHop
from exabgp.bgp.message.update.attribute.attribute import Attribute


# ================================================================== NextHop (3)

# The inheritance order is important and attribute MUST be first for the righ register to be called
# At least until we rename them to be more explicit

class NextHop (Attribute,IP):
	ID = Attribute.CODE.NEXT_HOP
	FLAG = Attribute.Flag.TRANSITIVE
	CACHING = True

	def __init__ (self, ip, packed=None):
		# Need to conform to from IP interface
		self.ip = ip
		self.packed = packed if packed else IP.create(ip).pack()

	def __eq__ (self, other):
		return \
			self.ID == other.ID and \
			self.FLAG == other.FLAG and \
			self.packed == other.packed

	def __ne__ (self, other):
		return not self.__eq__(other)

	def pack (self, negotiated=None):
		return self._attribute(self.packed)

	@classmethod
	def unpack (cls, data, negotiated=None):
		if not data:
			return NoNextHop
		return IP.unpack(data,NextHop)

	def __repr__ (self):
		return IP.__repr__(self)
