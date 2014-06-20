# encoding: utf-8
"""
encapsulation.py

Created by Thomas Mangin on 2014-06-20.
Copyright (c) 2014-2014 Orange. All rights reserved.
Copyright (c) 2014-2014 Exa Networks. All rights reserved.
"""

from struct import pack,unpack

from exabgp.bgp.message.update.attribute.community.extended import ExtendedCommunity


# ================================================================ Encapsulation

# RFC 5512, section 4.5

class Encapsulation (ExtendedCommunity):
	COMMUNITY_TYPE = 0x03
	COMMUNITY_SUBTYPE = 0x0c

	DEFAULT=0
	L2TPv3=1
	GRE=2
	VXLAN=3  # as in draft-sd-l2vpn-evpn-overlay-02, but value collides with reserved values in RFC5566
	NVGRE=4  # ditto
	IPIP=7

	encapType2String = {
		L2TPv3: "L2TPv3",
		GRE:    "GRE",
		VXLAN:  "VXLAN",
		NVGRE:  "NVGRE",
		IPIP:   "IP-in-IP",
		DEFAULT:"Default"
	}

	def __init__ (self,tunnel_type):
		self.tunnel_type = tunnel_type
		self.community = self.pack()

	def __str__ (self):
		if self.tunnel_type in Encapsulation.encapType2String:
			return "Encap:" + Encapsulation.encapType2String[self.tunnel_type]
		return "Encap:(unknown:%d)" % self.tunnel_type

	def __hash__ (self):
		return hash(self.community)

	def __cmp__ (self,other):
		if not isinstance(other,self.__class__):
			return -1
		if self.tunnel_type != other.tunnel_type:
			return -1
		return 0

	def pack (self):
		return pack("!BBHHH",
			Encapsulation.COMMUNITY_TYPE,
			Encapsulation.COMMUNITY_SUBTYPE,
			0,
			0,
			self.tunnel_type
		)

	@staticmethod
	def unpack (data):
		return Encapsulation(unpack('!H',data[6:8])[0])

		# type_  = ord(data[0]) & 0x0F
		# stype = ord(data[1])

		# assert(type_==Encapsulation.COMMUNITY_TYPE)
		# assert(stype==Encapsulation.COMMUNITY_SUBTYPE)
		# assert(len(data)==6)
