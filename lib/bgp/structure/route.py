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

from bgp.message.update import Update,NLRIS

from bgp.message.update.attributes import Attributes
from bgp.message.update.attribute import Attribute

from bgp.message.update.attribute.nexthop     import to_NextHop
from bgp.message.update.attribute.mprnlri     import MPRNLRI
from bgp.message.update.attribute.mpurnlri    import MPURNLRI

# This class must be separated from the wire representation of a Route
# =================================================================== Route

def to_Route (ip,netmask):
	return Route(to_Prefix(ip,netmask))

def new_Route (data,afi):
	nlri = new_NLRI(data,afi)
	return Route(nlri)

class Route (object):
	def __init__ (self,nlri):
		self.nlri = nlri
		self.attributes = Attributes()
		self._next_hop = None

	def _set_next_hop (self,nh):
		if self.nlri.afi == AFI.ipv4:
			self.attributes[Attribute.NEXT_HOP] = to_NextHop(nh)
		if self.nlri.afi == AFI.ipv6:
			self.attributes[Attribute.MP_REACH_NLRI] = MPRNLRI(AFI(self.nlri.afi),SAFI(self.nlri.safi),self)
		self._next_hop = to_IP(nh)
	def _get_next_hop (self):
		return self._next_hop
	next_hop = property(_get_next_hop,_set_next_hop)

	def announce (self,local_asn,remote_asn):
		if self.nlri.afi == AFI.ipv4:
			return Update(NLRIS(),NLRIS([self.nlri]),self.attributes).announce(local_asn,remote_asn)
		if self.nlri.afi == AFI.ipv6:
			return Update(NLRIS(),NLRIS(),self.attributes).announce(local_asn,remote_asn)

	def __str__ (self):
		next_hop = ''
		if self.next_hop:
			next_hop = ' next-hop %s' % str(self.next_hop)
		return "%s%s%s" % (self.nlri,next_hop,str(self.attributes))

