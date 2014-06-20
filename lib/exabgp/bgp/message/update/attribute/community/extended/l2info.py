# encoding: utf-8
"""
encapsulation.py

Created by Thomas Mangin on 2014-06-20.
Copyright (c) 2014-2014 Orange. All rights reserved.
Copyright (c) 2014-2014 Exa Networks. All rights reserved.
"""

from struct import pack,unpack

from exabgp.bgp.message.update.attribute.community.extended import ExtendedCommunity


# ============================================================ Layer2Information


class L2Info (ExtendedCommunity):
	COMMUNITY_TYPE = 0x00
	COMMUNITY_SUBTYPE = 0x0A

	def __init__ (self,encaps,control,mtu,reserved,community=None):
		self.encaps = encaps
		self.control = control
		self.mtu = mtu
		self.reserved = reserved
		self.community = community if community is not None else self.pack()

	def __str__ (self):
		return "L2info:%s:%s:%s:%s" % (self.encaps,self.control,self.mtu,self.reserved)

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
		encaps,control,mtu,reserved = unpack('!BBHH',data[2:8])
		return L2Info(encaps,control,mtu,reserved,data[:8])

L2Info._known[chr(L2Info.COMMUNITY_TYPE)+chr(L2Info.COMMUNITY_SUBTYPE)] = L2Info
