# encoding: utf-8
"""
nexthop.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2013 Exa Networks. All rights reserved.
"""

from exabgp.protocol.ip.inet import Inet,rawinet
from exabgp.bgp.message.update.attribute.id import AttributeID
from exabgp.bgp.message.update.attribute import Flag,Attribute

# =================================================================== NextHop (3)

# from struct import pack
# def cachedNextHop (afi,safi,packed):
# 	cache = pack('HB%ss' % len(packed),afi,safi,packed)
# 	if cache in NextHop.cache:
# 		return NextHop.cache[cache]
# 	instance = NextHop(afi,safi,packed)
# 	if NextHop.caching:
# 		NextHop.cache[cache] = instance
# 	return instance

def cachedNextHop (packed):
	if packed in NextHop.cache:
		return NextHop.cache[packed]
	instance = NextHop(packed)

	if NextHop.caching:
		NextHop.cache[packed] = instance
	return instance

class NextHop (Attribute):
	ID = AttributeID.NEXT_HOP
	FLAG = Flag.TRANSITIVE
	MULTIPLE = False

	cache = {}
	caching = False

	def __init__ (self,packed):
		self.packed = packed
		self._str = ''
		self._afi = None

	def pack (self):
		return self._attribute(self.packed)

	def afi (self):
		if not self._afi:
			inet = Inet(*rawinet(self.packed))
			self._str = str(inet)
			self._afi = inet.afi
		return self._afi

	def __str__ (self):
		if not self._str:
			inet = Inet(*rawinet(self.packed))
			self._str = str(inet)
			self._afi = inet.afi
		return self._str
