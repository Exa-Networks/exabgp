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

	class Type:
		DEFAULT = 0x00
		L2TPv3  = 0x01
		GRE     = 0x02
		VXLAN   = 0x03  # draft-sd-l2vpn-evpn-overlay-02, collides with reserved values in RFC5566
		NVGRE   = 0x04  # draft-sd-l2vpn-evpn-overlay-02, collides with reserved values in RFC5566
		IPIP    = 0x07

	_string = {
		Type.DEFAULT  : "Default",
		Type.L2TPv3   : "L2TPv3",
		Type.GRE      : "GRE",
		Type.VXLAN    : "VXLAN",
		Type.NVGRE    : "NVGRE",
		Type.IPIP     : "IP-in-IP",
	}

	def __init__ (self,tunnel_type,community=None):
		self.tunnel_type = tunnel_type
		self.community = community if community is not None else self.pack()

	def __str__ (self):
		return "Encapsulation: %s" % Encapsulation._string.get(self.tunnel_type,"Encap:(unknown:%d)" % self.tunnel_type)

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
			self.COMMUNITY_TYPE,
			self.COMMUNITY_SUBTYPE,
			0,
			0,
			self.tunnel_type
		)

	@staticmethod
	def unpack (data):
		return Encapsulation(unpack('!H',data[6:8])[0],data[:8])

		# type_  = ord(data[0]) & 0x0F
		# stype = ord(data[1])

		# assert(type_==Encapsulation.COMMUNITY_TYPE)
		# assert(stype==Encapsulation.COMMUNITY_SUBTYPE)
		# assert(len(data)==6)

Encapsulation._known[chr(Encapsulation.COMMUNITY_TYPE)+chr(Encapsulation.COMMUNITY_SUBTYPE)] = Encapsulation
