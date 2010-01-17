#!/usr/bin/env python
# encoding: utf-8
"""
route.py

Created by Thomas Mangin on 2010-01-16.
Copyright (c) 2010 Exa Networks. All rights reserved.
"""

from bgp.structure.afi import AFI
from bgp.structure.safi import SAFI

from bgp.message.inet import to_NLRI,to_IP
from bgp.message.update import Update,NLRIS

from bgp.message.update.attributes import Attributes
from bgp.message.update.attribute import Attribute

from bgp.message.update.attribute.nexthop     import to_NextHop
from bgp.message.update.attribute.mprnlri     import MPRNLRI
from bgp.message.update.attribute.mpurnlri    import MPURNLRI

# This class must be separated from the wire representation of a Route
# =================================================================== Route

def to_Route (ip,netmask):
	return Route(to_NLRI(ip,netmask))

def new_Route (data,afi):
	nlri = new_NLRI(data,afi)
	return Route(nlri)

class Route (object):
	def __init__ (self,nlri):
		self.nlri = nlri
		self.attributes = Attributes()

	def _set_next_hop (self,nh):
		self._next_hop = to_IP(nh)
	def _get_next_hop (self):
		return self._next_hop
	next_hop = property(_get_next_hop,_set_next_hop)

	def announce (self,local_asn,remote_asn):
		attributes = Attributes(self.attributes.copy())
		if self.nlri.afi == AFI.ipv4:
			if self.nlri.safi == SAFI.unicast:
				attributes[Attribute.NEXT_HOP] = to_NextHop(self.next_hop.ip())
			return Update(NLRIS(),NLRIS([self.nlri]),attributes).announce(local_asn,remote_asn)
		if self.nlri.afi == AFI.ipv6:
			attributes[Attribute.MP_REACH_NLRI] = MPRNLRI(AFI(self.nlri.afi),SAFI(self.nlri.safi),self)
			return Update(NLRIS(),NLRIS(),attributes).announce(local_asn,remote_asn)

	def update (self,local_asn,remote_asn):
		attributes = Attributes(self.attributes.copy())
		if self.nlri.afi == AFI.ipv4:
			attributes[Attribute.NEXT_HOP] = to_NextHop(self.next_hop)
		return Update(NLRIS(),NLRIS([self.nlri]),attributes).update(local_asn,remote_asn)

	def __str__ (self):
		origin = ''
		if self.attributes.has(Attribute.ORIGIN):
			origin = ' origin %s' % str(self.attributes[Attribute.ORIGIN]).lower()

		aspath = ''
		if self.attributes.has(Attribute.AS_PATH):
			aspath = ' %s' % str(self.attributes[Attribute.AS_PATH]).lower().replace('_','-')

		local_pref= ''
		if self.attributes.has(Attribute.LOCAL_PREFERENCE):
			l = self.attributes[Attribute.LOCAL_PREFERENCE]
			local_pref= ' local_preference %s' % l

		if self.attributes.has(Attribute.MULTI_EXIT_DISC):
			m = self.attributes[Attribute.MULTI_EXIT_DISC]
			local_pref= ' med %s' % m

		communities = ''
		if self.attributes.has(Attribute.COMMUNITY):
			communities = ' community %s' % str(self.attributes[Attribute.COMMUNITY])

		next_hop = ''
		if self.attributes.has(Attribute.NEXT_HOP):
			next_hop = ' next-hop %s' % str(self.attributes[Attribute.NEXT_HOP])
		elif self.next_hop:
			next_hop = ' next-hop %s' % str(self.next_hop)

		return "%s%s%s%s%s%s" % (self.nlri,next_hop,origin,aspath,local_pref,communities)

