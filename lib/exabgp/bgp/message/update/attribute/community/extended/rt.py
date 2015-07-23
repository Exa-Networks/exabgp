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


# ============================================================= RouteTargetASNIP
# RFC 4360 / RFC 7153

class RouteTargetASNIP (RouteTarget):
	COMMUNITY_TYPE = 0x00
	LIMIT = 4

	__slots__ = ['asn','ip']

	def __init__ (self, asn, ip, transitive, community=None):
		self.asn = asn
		self.ip = ip
		RouteTarget.__init__(
			self,
			community if community else pack(
				'!2sHL',
				self._packedTypeSubtype(transitive),
				asn,IPv4.pton(ip)
			)
		)

	def __str__ (self):
		return "target:%d:%s" % (self.asn,self.ip)

	@staticmethod
	def unpack (data):
		asn,ip = unpack('!H4s',data[2:8])
		return RouteTargetASNIP(ASN(asn),IPv4.ntop(ip),False,data[:8])


# ============================================================= RouteTargetIPASN
# RFC 4360 / RFC 7153

class RouteTargetIPASN (RouteTarget):
	COMMUNITY_TYPE = 0x01
	LIMIT = 6

	__slots__ = ['asn','ip']

	def __init__ (self, asn, ip, transitive, community=None):
		self.ip = ip
		self.asn = asn
		RouteTarget.__init__(
			self,
			community if community else pack(
				'!2s4sH',
				self._packedTypeSubtype(transitive),
				IPv4.pton(ip),asn
			)
		)

	def __str__ (self):
		return "target:%s:%s" % (self.ip, self.asn)

	@staticmethod
	def unpack (data):
		ip,asn = unpack('!4sH',data[2:8])
		return RouteTargetIPASN(IPv4.ntop(ip),ASN(asn),False,data[:8])


# ======================================================== RouteTargetASN4Number
# RFC 4360 / RFC 7153

class RouteTargetASN4Number (RouteTarget):
	COMMUNITY_TYPE = 0x02
	LIMIT = 6

	__slots__ = ['asn','ip']

	def __init__ (self, asn, number, transitive, community=None):
		self.asn = asn
		self.number = number
		RouteTarget.__init__(
			self,
			community if community else pack(
				'!2sLH',
				self._packedTypeSubtype(transitive),
				asn,number
			)
		)

	def __str__ (self):
		return "target:%dL:%s" % (self.asn, self.number)

	@staticmethod
	def unpack (data):
		asn,number = unpack('!LH',data[2:8])
		return RouteTargetASN4Number(ASN(asn),number,False,data[:8])
