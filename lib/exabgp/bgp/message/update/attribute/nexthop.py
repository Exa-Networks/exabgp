# encoding: utf-8
"""
nexthop.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2013 Exa Networks. All rights reserved.
"""
from struct import pack

from exabgp.protocol.ip.inet import Inet
from exabgp.bgp.message.update.attribute.id import AttributeID
from exabgp.bgp.message.update.attribute import Flag,Attribute

# =================================================================== NextHop (3)

def cachedNextHop (afi,safi,packed):
	cache = pack('HB%ss' % len(packed),afi,safi,packed)
	if cache in NextHop.cache:
		return NextHop.cache[cache]
	instance = NextHop(afi,safi,packed)
	if NextHop.caching:
		NextHop.cache[cache] = instance
	return instance

class NextHop (Attribute,Inet):
	ID = AttributeID.NEXT_HOP
	FLAG = Flag.TRANSITIVE
	MULTIPLE = False

	cache = {}
	caching = False

	# Take an IP as value
	def __init__ (self,afi,safi,packed):
		Inet.__init__(self,afi,safi,packed)

	def pack (self):
		return self._attribute(Inet.pack(self))

	def __str__ (self):
		return Inet.__str__(self)
