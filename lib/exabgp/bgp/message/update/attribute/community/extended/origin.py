# encoding: utf-8
"""
origin.py

Created by Thomas Mangin on 2014-06-20.
Copyright (c) 2014-2014 Orange. All rights reserved.
Copyright (c) 2014-2014 Exa Networks. All rights reserved.
"""


import socket
from struct import pack,unpack

from exabgp.bgp.message.open.asn import ASN
from exabgp.bgp.message.update.attribute.community.extended import ExtendedCommunity


# ======================================================================= Origin
# RFC 4360 / RFC 7153

class Origin (ExtendedCommunity):
	COMMUNITY_SUBTYPE = 0x01

	@property
	def la (self):
		return self.community[2:self.LIMIT]

	@property
	def ga (self):
		return self.community[self.LIMIT:8]


# ================================================================== OriginASNIP
# RFC 4360 / RFC 7153

class OriginASNIP (Origin):
	COMMUNITY_TYPE = 0x00
	LIMIT = 4

	def __init__ (self,asn,ip,transitive,community=None):
		self.asn = asn
		self.ip = ip
		OriginASNIP.__init__(community if community else pack('!BBH4s',self.COMMUNITY_TYPE|0x40 if transitive else self.COMMUNITY_TYPE,0x02,asn,socket.inet_pton(socket.AF_INET,ip)))

	def __str__ (self):
		return "origin:%s:%d" % (self.asn,self.ip)

	@staticmethod
	def unpack(data):
		asn,ip = unpack('!H4s',data[2:8])
		return OriginASNIP(ASN(asn),socket.inet_ntop(socket.AF_INET,ip),False,data[:8])

OriginASNIP._known[(OriginASNIP.COMMUNITY_TYPE&0x0F,OriginASNIP.COMMUNITY_SUBTYPE)] = OriginASNIP


# ================================================================== OriginIPASN
# RFC 4360 / RFC 7153

class OriginIPASN (Origin):
	COMMUNITY_TYPE = 0x01
	LIMIT = 6

	def __init__ (self,asn,ip,transitive,community=None):
		self.ip = ip
		self.asn = asn
		OriginIPASN.__init__(community if community else pack('!BB4sH',self.COMMUNITY_TYPE|0x40 if transitive else self.COMMUNITY_TYPE,0x02,socket.inet_pton(socket.AF_INET,ip),asn))

	def __str__ (self):
		return "origin:%s:%d" % (self.ip, self.asn)

	@staticmethod
	def unpack (data):
		ip,asn = unpack('!4sH',data[2:8])
		return OriginIPASN(socket.inet_ntop(socket.AF_INET,ip),ASN(asn),False,data[:8])

OriginIPASN._known[(OriginIPASN.COMMUNITY_TYPE&0x0F,OriginIPASN.COMMUNITY_SUBTYPE)] = OriginIPASN


# ======================================================== OriginASN4Number
# RFC 4360 / RFC 7153

class OriginASN4Number (Origin):
	COMMUNITY_TYPE = 0x02
	LIMIT=6

	def __init__ (self,asn,number,transitive,community=None):
		self.asn = asn
		self.number = number
		OriginASN4Number.__init__(community if community else pack('!BBLH',self.COMMUNITY_TYPE|0x40 if transitive else self.COMMUNITY_TYPE,0x02,asn,number))

	def __str__ (self):
		return "origin:%s:%d" % (self.asn, self.number)

	@staticmethod
	def unpack (data):
		asn,number = unpack('!LH',data[2:8])
		return OriginASN4Number(ASN(asn),number,False,data[:8])

OriginASN4Number._known[(OriginASN4Number.COMMUNITY_TYPE&0x0F,OriginASN4Number.COMMUNITY_SUBTYPE)] = OriginASN4Number
