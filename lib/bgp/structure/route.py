#!/usr/bin/env python
# encoding: utf-8
"""
route.py

Created by Thomas Mangin on 2010-01-16.
Copyright (c) 2010 Exa Networks. All rights reserved.
"""

from bgp.structure.afi import AFI
from bgp.structure.safi import SAFI
from bgp.structure.ip import to_Prefix,to_IP
from bgp.structure.nlri import NLRI

from bgp.message.update import Update,NLRIS

from bgp.message.update.attributes import Attributes
from bgp.message.update.attribute import Attribute

from bgp.message.update.attribute.nexthop     import to_NextHop
from bgp.message.update.attribute.mprnlri     import MPRNLRI
from bgp.message.update.attribute.mpurnlri    import MPURNLRI

# This class must be separated from the wire representation of a Route
# =================================================================== Route

def to_Route (ip,netmask):
	prefix = to_Prefix(ip,netmask)
	return Route(prefix.afi,prefix.safi,prefix)

class Route (NLRI,Attributes):
	def __init__ (self,afi,safi,nlri):
		NLRI.__init__(self,afi,safi,nlri)
		self.nlri = nlri
		self._next_hop = None

	def _set_next_hop (self,nh):
		if self.nlri.afi == AFI.ipv4:
			self[Attribute.NEXT_HOP] = to_NextHop(nh)
		if self.nlri.afi == AFI.ipv6:
			self[Attribute.MP_REACH_NLRI] = MPRNLRI(AFI(self.afi),SAFI(self.safi),self)
		self._next_hop = to_IP(nh)
	def _get_next_hop (self):
		return self._next_hop
	next_hop = property(_get_next_hop,_set_next_hop)

	def update (self):
		if self.nlri.afi == AFI.ipv4:
			return Update(NLRIS(),NLRIS([self.nlri]),self)
		if self.nlri.afi == AFI.ipv6:
			return Update(NLRIS(),NLRIS(),self)

	def __str__ (self):
		next_hop = ''
		if self.next_hop:
			next_hop = ' next-hop %s' % str(self.next_hop)
		return "%s%s%s" % (self.nlri,next_hop,Attributes.__str__(self))

