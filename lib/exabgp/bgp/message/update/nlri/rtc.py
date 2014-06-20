# encoding: utf-8
"""
rtc.py

Created by Orange.
Copyright (c) 2014, Orange. All rights reserved.
"""

from struct import pack,unpack

from exabgp.structure.asn import ASN
from exabgp.structure.address import AFI,SAFI
from exabgp.message.update.attribute.community import RouteTarget

class RouteTargetConstraint(object):
	# TODO: no support yet for RTC variable length with prefixing

	def __init__(self,afi,safi,origin_as,route_target):
		self.afi = AFI(afi)
		self.safi = SAFI(safi)
		self.origin_as = origin_as
		self.route_target = route_target

	def __len__(self):
		if self.route_target is None:
			return 1
		else:
			return (4 + len(self.route_target))*8

	def __str__ (self):
		if self.route_target is None:
			return "RTC Wildcard"
		else:
			return "RTC<%s>:%s" % (self.origin_as,self.route_target)

	def __repr__(self):
		return self.__str__()

	def __cmp__(self,other):
		if (isinstance(other,RouteTargetConstraint) and
			self.origin_as == other.origin_as and
			self.route_target == other.route_target):
			return 0
		else:
			return -1

	def __hash__(self):
		return hash(self.pack())


	def pack(self):
		if self.route_target == None:
			return pack("!B",0)
		else:
			return pack("!BL", len(self), self.origin_as) + self.route_target.pack()

	@staticmethod
	def unpack(afi,safi,data):
		len_in_bits = ord(data[0])
		data=data[1:]

		if (len_in_bits==0):
			return RouteTargetConstraint(afi,safi,ASN(0),None)

		if (len_in_bits<4):
			raise Exception("RTC route too short to be decoded")

		asn = ASN(unpack('!L', data[0:4])[0])
		data = data[4:]

		rt = RouteTarget.unpackFrom(data)
		return RouteTargetConstraint(afi,safi,asn,rt)
