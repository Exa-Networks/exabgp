# encoding: utf-8
"""
mprnlri.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2013 Exa Networks. All rights reserved.
"""

from exabgp.protocol.ip.address import Address  # ,AFI,SAFI
from exabgp.bgp.message.update.attribute.id import AttributeID
from exabgp.bgp.message.update.attribute import Flag,Attribute

# =================================================================== MP Unreacheable NLRI (15)

class MPRNLRI (Attribute):
	FLAG = Flag.OPTIONAL
	ID = AttributeID.MP_REACH_NLRI
	MULTIPLE = True

	def __init__ (self,routes):
		# all the routes must have the same next-hop
		self.routes = routes

	def pack (self,addpath):
		next_hop = ''
		# EOR do not have any next_hop
		if self.routes[0].attributes.has(AttributeID.NEXT_HOP):
			# we do not want a next_hop attribute packed (with the _attribute()) but just the next_hop itself
			next_hop = self.routes[0].attributes[AttributeID.NEXT_HOP].packed
			if self.routes[0].nlri.safi.has_rd():
				next_hop = chr(0)*8 + next_hop
		routes = ''.join([route.nlri.pack(addpath) for route in self.routes])
		return self._attribute(
			self.routes[0].nlri.afi.pack() + self.routes[0].nlri.safi.pack() +
			chr(len(next_hop)) + next_hop +
			chr(0) + routes
		)

	def __len__ (self):
		return len(self.pack())

	def __str__ (self):
		return "MP_REACH_NLRI Family %s %d NLRI(s)" % (Address.__str__(self.routes[0]),len(self.routes))
