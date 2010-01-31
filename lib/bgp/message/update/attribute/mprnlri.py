#!/usr/bin/env python
# encoding: utf-8
"""
mprnlri.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009 Exa Networks. All rights reserved.
"""

from bgp.utils import *
from bgp.structure.address import Address
from bgp.message.update.attribute import AttributeID,Flag,Attribute

# =================================================================== MP Unreacheable NLRI (15)

class MPRNLRI (Address,Attribute):
	FLAG = Flag.OPTIONAL
	ID = AttributeID.MP_REACH_NLRI    
	MULTIPLE = True

	def __init__ (self,afi,safi,route):
		Address.__init__(self,afi,safi)
		self.route = route

	def pack (self):
		next_hop = ''
		if self.route.has_key(AttributeID.NEXT_HOP):
			# we do not want a next_hop attribute packed (with the _attribute()) but just the next_hop itself
			next_hop = self.route[AttributeID.NEXT_HOP].next_hop.pack()
		
		return self._attribute(
			self.afi.pack() + self.safi.pack() + 
			chr(len(next_hop)) + next_hop + 
			chr(0) + self.route.nlri.pack()
		)

	def __len__ (self):
		return len(self.pack())

	def __str__ (self):
		return "MP_REACH_NLRI Family %s NLRI %s" % (Address.__str__(self),str(self.attribute))
