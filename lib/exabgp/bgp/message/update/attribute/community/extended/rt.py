# encoding: utf-8
"""
rt.py

Created by Thomas Mangin on 2014-06-20.
Copyright (c) 2014-2014 Orange. All rights reserved.
"""


import socket
from struct import pack,unpack

from exabgp.bgp.message.open.asn import ASN
from exabgp.bgp.message.update.attribute.community.extended import ExtendedCommunity

# ================================================================== RouteTarget

class RouteTarget (ExtendedCommunity):
	COMMUNITY_TYPE = 0x00
	COMMUNITY_SUBTYPE = 0x02

	def __init__ (self,asn,ip,number):
		assert (asn is None or ip is None)
		assert (asn is not None or ip is not None)

		if not asn is None:
			self.asn = asn
			self.number = number
			self.ip = ""
		else:
			self.ip = ip
			self.number = number
			self.asn = 0

		self.community = self.pack()

	def pack (self):
		if self.asn is not None:
			# type could also be 0x02 -> FIXME check RFC
			#return pack( 'BB!H!L', 0x00,0x02, self.asn, self.number)
			return pack('!BBHL',0x00,0x02,self.asn,self.number)
		else:
			encoded_ip = socket.inet_pton(socket.AF_INET,self.ip)
			return pack('!BB4sH',0x01,0x02,encoded_ip,self.number)

	def __str__ (self):
		if self.asn is not None:
			return "target:%s:%d" % (str(self.asn), self.number)
		else:
			return "target:%s:%d" % (self.ip, self.number)

	def __cmp__ (self,other):
		if not isinstance(other,self.__class__):
			return -1
		if self.asn != other.asn:
			return -1
		if self.ip != other.ip:
			return -1
		if self.number != other.number:
			return -1
		return 0

	def __hash__ (self):
		return hash(self.community)

	@staticmethod
	def unpack(data):
		type_  = ord(data[0]) & 0x0F
		stype = ord(data[1])
		data = data[2:]

		if stype == 0x02:  # XXX: FIXME: unclean
			if type_ in (0x00,0x02):
				asn,number = unpack('!HL',data[:6])
				return RouteTarget(ASN(asn),None,number)
			if type_ == 0x01:
				ip = socket.inet_ntop(data[0:4])
				number = unpack('!H',data[4:6])[0]
				return RouteTarget(None,ip,number)
