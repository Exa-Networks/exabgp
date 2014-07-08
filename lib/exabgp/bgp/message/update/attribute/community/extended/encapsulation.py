# encoding: utf-8
"""
encapsulation.py

Created by Thomas Mangin on 2014-06-20.
Copyright (c) 2014-2014 Orange. All rights reserved.
Copyright (c) 2014-2014 Exa Networks. All rights reserved.
"""

from struct import pack
from struct import unpack

from exabgp.bgp.message.update.attribute.community.extended import ExtendedCommunity

# ================================================================ Encapsulation
# RFC 5512

class Encapsulation (ExtendedCommunity):
	COMMUNITY_TYPE = 0x03
	COMMUNITY_SUBTYPE = 0x0C

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

	__slots__ = ['tunnel_type']

	def __init__ (self,tunnel_type,community=None):
		self.tunnel_type = tunnel_type
		ExtendedCommunity.__init__(self,community if community is not None else pack("!BBLH",0x03,0x0C,0,self.tunnel_type))

	def __str__ (self):
		return "Encapsulation: %s" % Encapsulation._string.get(self.tunnel_type,"Encap:(unknown:%d)" % self.tunnel_type)

	@staticmethod
	def unpack (data):
		tunnel, = unpack('!H',data[6:8])
		return Encapsulation(tunnel,data[:8])

		# type_  = ord(data[0]) & 0x0F
		# stype = ord(data[1])

		# assert(type_==Encapsulation.COMMUNITY_TYPE)
		# assert(stype==Encapsulation.COMMUNITY_SUBTYPE)
		# assert(len(data)==6)

Encapsulation.register_extended()
