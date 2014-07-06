# encoding: utf-8
"""
nexthop.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2013 Exa Networks. All rights reserved.
"""

from exabgp.protocol.ip import IPv4
from exabgp.bgp.message.update.attribute.id import AttributeID
from exabgp.bgp.message.update.attribute import Flag,Attribute

# ================================================================== NextHop (3)

# The order is important and attribute MUST be first for the righ register to be called
# At least until we rename them to be more explicit

class NextHop (Attribute,IPv4):
	ID = AttributeID.NEXT_HOP
	FLAG = Flag.TRANSITIVE
	MULTIPLE = False
	CACHING = True

	cache = {}
	caching = False

	# __init__ inherited from IPv4

	def pack (self,asn4=None):
		return self._attribute(self.packed)

	def __cmp__(self,other):
		if not isinstance(other,self.__class__):
			return -1
		if self.pack() != other.pack():
			return -1
		return 0

	@staticmethod
	def unpack (data,negotiated):
		if data in NextHop.cache:
			return NextHop.cache[data]
		instance = IPv4.unpack(data,NextHop)

		if NextHop.caching:
			NextHop.cache[data] = instance
		return instance


NextHop.register()
