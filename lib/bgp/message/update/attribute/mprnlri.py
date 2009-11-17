#!/usr/bin/env python
# encoding: utf-8
"""
mprnlri.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009 Exa Networks. All rights reserved.
"""

from bgp.utils import *
from bgp.message.inet import AFI,SAFI
from bgp.message.update.attribute.parent import Attribute,Flag

# =================================================================== MP Unreacheable NLRI (15)

class MPRNLRI (Attribute):
	FLAG = Flag.TRANSITIVE
	ID = Attribute.MP_REACH_NLRI    
	MULTIPLE = True

	# init takes a Route ...

	def pack (self):
		nlri = self.value.nlri.pack()
		next_hop = self.value.next_hop
		return self._attribute(
			AFI(AFI.ipv6).pack() + SAFI(SAFI.unicast).pack() + 
			chr(len(next_hop)) + next_hop + 
			chr(0) + nlri
		)

	def __len__ (self):
		return len(self.pack())

	def __str__ (self):
		return "MP Reacheable NLRI"

## The past :)
##		message += self._attribute(Flag.TRANSITIVE,ORIGIN,Origin(Origin.IGP).pack())
##		message += self._attribute(Flag.TRANSITIVE,AS_PATH,'' if local_asn == peer_asn else self._segment(ASPath.AS_SEQUENCE,[local_asn]))
##		if local_asn == peer_asn:
##			message += self._attribute(Flag.TRANSITIVE,LOCAL_PREFERENCE,self.local_preference.pack())
##		message += self._attribute(Flag.TRANSITIVE|Flag.OPTIONAL,COMMUNITY,''.join([c.pack() for c in self.communities])) if self.communities else ''
##		if self.nlri.afi == AFI.ipv4:
##			message += self._attribute(Flag.TRANSITIVE,NEXT_HOP,self.next_hop.pack())
##		if self.nlri.afi == AFI.ipv6:
##			if mp_action == '-':
##				attr = AFI(AFI.ipv6).pack() + SAFI(SAFI.unicast).pack() + Prefix.pack(self)
##				message += self._attribute(Flag.TRANSITIVE,MP_UNREACH_NLRI,attr)
##			if mp_action == '+':
##				prefix = self.nlri.pack()
##				next_hop = self.next_hop.pack()
##				attr = AFI(AFI.ipv6).pack() + SAFI(SAFI.unicast).pack() + chr(len(next_hop)) + next_hop + chr(0) + prefix
##				message += self._attribute(Flag.TRANSITIVE,MP_REACH_NLRI,attr)
##		return message
#
