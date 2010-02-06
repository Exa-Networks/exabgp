#!/usr/bin/env python
# encoding: utf-8
"""
mprnlri.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009 Exa Networks. All rights reserved.
"""

from bgp.structure.address import Address
from bgp.message.update.attribute import AttributeID,Flag,Attribute

# =================================================================== MP Unreacheable NLRI (15)

class MPRNLRI (Attribute):
	FLAG = Flag.OPTIONAL
	ID = AttributeID.MP_REACH_NLRI    
	MULTIPLE = True

	def __init__ (self,routes):
		# all the routes must have the same next-hop
		self.routes = routes

	def pack (self):
		next_hop = ''
		# EOR do not have any next_hop
		if self.routes[0].has_key(AttributeID.NEXT_HOP):
			# we do not want a next_hop attribute packed (with the _attribute()) but just the next_hop itself
			next_hop = self.routes[0][AttributeID.NEXT_HOP].next_hop.pack()
		routes = ''.join([route.nlri.pack() for route in self.routes])

		return self._attribute(
			self.routes[0].afi.pack() + self.routes[0].safi.pack() + 
			chr(len(next_hop)) + next_hop + 
			chr(0) + routes
		)

	def __len__ (self):
		return len(self.pack())

	def __str__ (self):
		return "MP_REACH_NLRI Family %s %d NLRI(s)" % (Address.__str__(self.routes[0]),len(self.routes))
