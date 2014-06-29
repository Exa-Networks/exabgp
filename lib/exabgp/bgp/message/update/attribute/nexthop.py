# encoding: utf-8
"""
nexthop.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2013 Exa Networks. All rights reserved.
"""

from exabgp.protocol.ip import IP
from exabgp.bgp.message.update.attribute.id import AttributeID
from exabgp.bgp.message.update.attribute import Flag,Attribute

# ================================================================== NextHop (3)

class NextHop (Attribute,IP):
	ID = AttributeID.NEXT_HOP
	FLAG = Flag.TRANSITIVE
	MULTIPLE = False

	cache = {}
	caching = False

	# __init__ inherited from Inet

	def pack (self,asn4=None):
		return self._attribute(self.packed)

	def __cmp__(self,other):
		if not isinstance(other,self.__class__):
			return -1
		if self.pack() != other.pack():
			return -1
		return 0

	@staticmethod
	def unpack (data):
		# XXX: FIXME: this should not be needed ! ?
		if not data:
			return data

		if data in NextHop.cache:
			return NextHop.cache[data]
		instance = IP.unpack(data,NextHop)

		if NextHop.caching:
			NextHop.cache[data] = instance
		return instance
