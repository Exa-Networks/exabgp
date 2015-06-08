# encoding: utf-8
"""
encapsulation.py

Created by Thomas Mangin on 2014-06-20.
Copyright (c) 2014-2015 Orange. All rights reserved.
Copyright (c) 2014-2015 Exa Networks. All rights reserved.
"""

from struct import pack
from struct import unpack

from exabgp.bgp.message.update.attribute.community.extended import ExtendedCommunity

# ================================================================ Encapsulation
# RFC 5512


@ExtendedCommunity.register
class Encapsulation (ExtendedCommunity):
	COMMUNITY_TYPE = 0x03
	COMMUNITY_SUBTYPE = 0x0C

	# https://www.iana.org/assignments/bgp-parameters/bgp-parameters.xhtml#tunnel-types
	class Type:
		DEFAULT   = 0x00
		L2TPv3    = 0x01
		GRE       = 0x02
		IPIP      = 0x07
		VXLAN     = 0x08
		NVGRE     = 0x09
		MPLS      = 0x0A
		VXLAN_GPE = 0x0C
		MPLS_UDP  = 0x0D

	_string = {
		Type.DEFAULT:   "Default",
		Type.L2TPv3:    "L2TPv3",
		Type.GRE:       "GRE",
		Type.IPIP:      "IP-in-IP",
		Type.VXLAN:     "VXLAN",
		Type.NVGRE:     "NVGRE",
		Type.MPLS:      "MPLS",
		Type.VXLAN_GPE: "VXLAN-GPE",
		Type.MPLS_UDP:  "MPLS-in-UDP",
	}

	__slots__ = ['tunnel_type']

	def __init__ (self, tunnel_type, community=None):
		self.tunnel_type = tunnel_type
		ExtendedCommunity.__init__(
			self,community if community is not None else pack(
				"!2sLH",
				self._subtype(),
				0,self.tunnel_type
			)
		)

	def __repr__ (self):
		return "Encap:%s" % Encapsulation._string.get(self.tunnel_type,"Encap:(unknown:%d)" % self.tunnel_type)

	@staticmethod
	def unpack (data):
		tunnel, = unpack('!H',data[6:8])
		return Encapsulation(tunnel,data[:8])

		# type_  = ord(data[0]) & 0x0F
		# stype = ord(data[1])

		# assert(type_==Encapsulation.COMMUNITY_TYPE)
		# assert(stype==Encapsulation.COMMUNITY_SUBTYPE)
		# assert(len(data)==6)
