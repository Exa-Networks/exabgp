# encoding: utf-8
"""
rt.py

Created by Thomas Mangin on 2014-06-20.
Copyright (c) 2014-2015 Orange. All rights reserved.
Copyright (c) 2014-2015 Exa Networks. All rights reserved.
"""

from struct import pack
from struct import unpack

from exabgp.protocol.ip import IPv4
from exabgp.bgp.message.open.asn import ASN
from exabgp.bgp.message.update.attribute.attribute import Attribute
from exabgp.bgp.message.update.attribute.community.extended import ExtendedCommunity


# ================================================================== RouteTarget
# RFC 4360 / RFC 7153

class RouteTarget (ExtendedCommunity):
	COMMUNITY_SUBTYPE = 0x02
	LIMIT = 0

	@property
	def la (self):
		return self.community[2:self.LIMIT]

	@property
	def ga (self):
		return self.community[self.LIMIT:8]

	def __eq__(self,other):
		return self.__cmp__(other) == 0

	def __neq__(self,other):
		return self.__cmp__(other) != 0


# ============================================================= RouteTargetASN2Number
# RFC 4360 / RFC 7153

class RouteTargetASN2Number (RouteTarget):
	COMMUNITY_TYPE = 0x00
	LIMIT = 4

	__slots__ = ['asn','number']

	def __init__ (self, asn, number, transitive=True, community=None):
		self.asn = asn
		self.number = number
		# assert(number < pow(2,32))
		RouteTarget.__init__(
			self,
			community if community else pack(
				'!BBHL',
				self.COMMUNITY_TYPE | Attribute.Flag.TRANSITIVE if transitive else self.COMMUNITY_TYPE,0x02,
				asn,number
			)
		)

	def __hash__(self):
		return hash((self.asn,self.number))

	def __cmp__(self,other):
		if not isinstance(other,self.__class__):
			return RouteTarget.__cmp__(self, other)
		# compare need to not take into account the attribute flags
		return cmp((self.asn,self.number),(other.asn,other.number))

	def __repr__ (self):
		return "target:%d:%d" % (self.asn,self.number)

	@staticmethod
	def unpack (data):
		asn,number = unpack('!HL',data[2:8])
		return RouteTargetASN2Number(ASN(asn),number,False,data[:8])


# ============================================================= RouteTargetIPNumber
# RFC 4360 / RFC 7153

class RouteTargetIPNumber (RouteTarget):
	COMMUNITY_TYPE = 0x01
	LIMIT = 6

	__slots__ = ['ip','number']

	def __init__ (self, ip, number, transitive=True, community=None):
		self.ip = ip
		self.number = number
		# assert(number < pow(2,16))
		RouteTarget.__init__(
			self,
			community if community else pack(
				'!BB4sH',
				self.COMMUNITY_TYPE | Attribute.Flag.TRANSITIVE if transitive else self.COMMUNITY_TYPE,0x02,
				IPv4.pton(ip),number
			)
		)

	def __hash__(self):
		return hash((self.ip,self.number))

	def __cmp__(self,other):
		if not isinstance(other,self.__class__):
			return RouteTarget.__cmp__(self, other)
		return cmp((self.ip,self.number),(other.ip,other.number))

	def __repr__ (self):
		return "target:%s:%d" % (self.ip, self.number)

	@staticmethod
	def unpack (data):
		ip,number = unpack('!4sH',data[2:8])
		return RouteTargetIPNumber(IPv4.ntop(ip),number,False,data[:8])


# ======================================================== RouteTargetASN4Number
# RFC 4360 / RFC 7153

class RouteTargetASN4Number (RouteTarget):
	COMMUNITY_TYPE = 0x02
	LIMIT = 6

	__slots__ = ['asn','number']

	def __init__ (self, asn, number, transitive=True, community=None):
		self.asn = asn
		self.number = number
		# assert(number < pow(2,16))
		RouteTarget.__init__(
			self,
			community if community else pack(
				'!BBLH',
				self.COMMUNITY_TYPE | Attribute.Flag.TRANSITIVE if transitive else self.COMMUNITY_TYPE,0x02,
				asn,number
			)
		)

	def __hash__(self):
		return hash((self.asn,self.number))

	def __cmp__(self,other):
		if not isinstance(other,self.__class__):
			return RouteTarget.__cmp__(self, other)
		return cmp((self.asn,self.number),(other.asn,other.number))

	def __repr__ (self):
		return "target:%dL:%d" % (self.asn, self.number)

	@staticmethod
	def unpack (data):
		asn,number = unpack('!LH',data[2:8])
		return RouteTargetASN4Number(ASN(asn),number,False,data[:8])
