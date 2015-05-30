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
from exabgp.bgp.message.update.attribute.attribute import Attribute
from exabgp.bgp.message.update.attribute.community.extended.rt import RouteTarget

from exabgp.protocol.ip import IP
from exabgp.protocol.ip import NoNextHop

from exabgp.protocol.family import AFI
from exabgp.protocol.family import SAFI

from exabgp.bgp.message.update.nlri.nlri import NLRI


@NLRI.register(AFI.ipv4,SAFI.rtc)
class RouteTargetConstraint (NLRI):
	# XXX: FIXME: no support yet for RTC variable length with prefixing

	__slots__ = ['origin','rt','action','nexthop']

	def __init__ (self, afi, safi, action, nexthop, origin, rt):
		NLRI.__init__(self,afi,safi)
		self.action = action
		self.nexthop = IP.unpack(nexthop) if nexthop else NoNextHop
		self.origin = origin
		self.rt = rt

	def __eq__ (self, other):
		return \
			NLRI.__eq__(self,other) and \
			self.action == other.action and \
			self.nexthop == other.action and \
			self.origin == other.origin and \
			self.rt == other.rt

	def __ne__ (self, other):
		return not self.__eq__(other)

	def __len__ (self):
		return (4 + len(self.rt))*8 if self.rt else 1

	def __str__ (self):
		return "rtc %s:%s" % (self.origin,self.rt) if self.rt else "rtc wildcard"

	def __repr__ (self):
		return str(self)

	def __hash__ (self):
		return hash(self.pack())

	@staticmethod
	def resetFlags(char):
		return chr(ord(char) & ~(Attribute.Flag.TRANSITIVE | Attribute.Flag.OPTIONAL))

	def pack (self, addpath=None):
		# XXX: no support for addpath yet
		packedRT = self.rt.pack()
		# We reset ext com flag bits from the first byte in the packed RT
		# because in an RTC route these flags never appear.
		if self.rt:
			return pack("!BLB", len(self), self.origin, ord(RouteTargetConstraint.resetFlags(packedRT[0]))) + packedRT[1:]
		return pack("!B",0)

	@classmethod
	def unpack (cls, afi, safi, data, addpath, nexthop, action):
		length = ord(data[0])

		if length == 0:
			return 1,RouteTargetConstraint(afi,safi,action,ASN(0),None)

		# safeguard: let's ignore any ext com flag that might be set here
		packedRT = RouteTargetConstraint.resetFlags(data[5])+data[6:13]

		return 13,RouteTargetConstraint(
			afi, safi, action, nexthop,
			ASN(unpack('!L', data[1:5])[0]),
			RouteTarget.unpack(packedRT)
		)
