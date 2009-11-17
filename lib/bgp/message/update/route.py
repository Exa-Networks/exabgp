#!/usr/bin/env python
# encoding: utf-8
"""
route.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009 Exa Networks. All rights reserved.
"""

from bgp.utils import *
from bgp.message.inet import to_NLRI, NLRI
from bgp.message.inet import AFI,SAFI
from bgp.message.update.attribute.nexthop import NextHop, to_NextHop
from bgp.message.update.attribute.parent import Attribute,Flag
from bgp.message.update.attribute.attributes import Attributes
from bgp.message.update.attribute.mprnlri  import MPRNLRI
from bgp.message.update.attribute.mpurnlri import MPURNLRI
from bgp.message.update.update import Update,NLRIS

# =================================================================== Route

def to_Route (ip,netmask):
	return Route(to_NLRI(ip,netmask))

class Route (object):
	def __init__ (self,nlri):
		self.nlri = nlri
		self.attributes = Attributes()

	def _set_next_hop (self,nh):
		self._next_hop = to_IP(nh)
	def _get_next_hop (self):
		return self._next_hop
	property = (_get_next_hop,_set_next_hop)

	def announce (self,local_asn,remote_asn):
		attributes = Attributes(self.attributes.copy())
		if self.nlri.afi == AFI.ipv4:
			attributes[Attribute.NEXT_HOP] = to_NextHop(self.next_hop)
			return Update(NLRIS(),NLRIS([self.nlri]),attributes).announce(local_asn,remote_asn)
		if self.nlri.afi == AFI.ipv6:
			attributes[Attribute.NEXT_HOP] = to_NextHop('0.0.0.0')
			attributes[Attribute.MP_REACH_NLRI] = MPRNLRI(self)
			return Update(NLRIS(),NLRIS(),attributes).announce(local_asn,remote_asn)

	def update (self,local_asn,remote_asn):
		attributes = Attributes(self.attributes.copy())
		if self.nlri.afi == AFI.ipv4:
			attributes[Attribute.NEXT_HOP] = to_NextHop(self.next_hop)
		return Update(NLRIS(),NLRIS([self.nlri]),attributes).update(local_asn,remote_asn)

	def __str__ (self):
		local_pref= ''

		if self.attributes.has(Attribute.LOCAL_PREFERENCE):
			l = self.attributes[Attribute.LOCAL_PREFERENCE]
			if l == 100: # XXX: Double check default Local Pref
				local_pref= ' local_preference %s' % l

		communities = ''
		if self.attributes.has(Attribute.COMMUNITY):
			communities = ' community %s' % str(self.attributes[Attribute.COMMUNITY])

		next_hop = ''
		if self.attributes.has(Attribute.NEXT_HOP):
			next_hop = ' next-hop %s' % str(self.attributes[Attribute.NEXT_HOP])

		return "%s%s%s%s" % (self.nlri,next_hop,local_pref,communities)
