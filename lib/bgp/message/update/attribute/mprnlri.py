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
	FLAG = Flag.OPTIONAL
	ID = Attribute.MP_REACH_NLRI    
	MULTIPLE = True

	def __init__ (self,afi,safi,route):
		Attribute.__init__(self,(afi,safi,route))

	# XXX: For flow route we may have to really remove the NEXT_HOP which is recommended anyway
	def pack (self):
		afi,safi,route = self.value
		nlri = route.nlri.pack()
		next_hop = route.next_hop.pack()
		return self._attribute(
			afi.pack() + safi.pack() + 
			chr(len(next_hop)) + next_hop + 
			chr(0) + nlri
		)

	def __len__ (self):
		return len(self.pack())

	def __str__ (self):
		return "MP Reacheable NLRI %s" % str(self.value)
