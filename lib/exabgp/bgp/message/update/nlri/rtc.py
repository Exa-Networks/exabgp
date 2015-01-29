# encoding: utf-8
"""
rtc.py

Created by Thomas Morin on 2014-06-10.
Copyright (c) 2014-2015 Orange. All rights reserved.
Copyright (c) 2014-2015 Exa Networks. All rights reserved.
"""

from struct import pack
from struct import unpack

from exabgp.bgp.message.open.asn import ASN
from exabgp.bgp.message.update.attribute.community.extended.rt import RouteTarget
from exabgp.protocol.ip.address import Address


class RouteTargetConstraint(Address):
	# XXX: FIXME: no support yet for RTC variable length with prefixing

	__slots__ = ['origin','rt']

	def __init__ (self, afi, safi, origin, rt):
		Address.__init__(self,afi,safi)
		self.origin = origin
		self.rt = rt

	def __len__ (self):
		return (4 + len(self.rt))*8 if self.rt else 1

	def __str__ (self):
		return "rtc %s:%s" % (self.origin,self.rt) if self.rt else "rtc wildcard"

	def __repr__ (self):
		return str(self)

	def __cmp__ (self, other):
		if not isinstance(other,self.__class__):
			return -1
		if self.origin != other.origin:
			return -1
		if self.rt != other.rt:
			return -1
		return 0

	def __hash__ (self):
		return hash(self.pack())

	def pack (self):
		if self.rt:
			return pack("!BL", len(self), self.origin) + self.rt.pack()
		return pack("!B",0)

	@staticmethod
	def unpack (afi, safi, data):
		length = ord(data[0])

		if length == 0:
			return RouteTargetConstraint(afi,safi,ASN(0),None)

		return RouteTargetConstraint(
			afi,safi,
			ASN(unpack('!L', data[1:5])[0]),
			RouteTarget.unpack(data[5:])
		)
