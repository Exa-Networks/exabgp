# encoding: utf-8
"""
mprnlri.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2013 Exa Networks. All rights reserved.
"""

from exabgp.protocol.ip.address import Address
from exabgp.bgp.message.update.attribute.id import AttributeID
from exabgp.bgp.message.update.attribute import Flag,Attribute

# =================================================================== MP NLRI (14)

class MPURNLRI (Attribute):
	FLAG = Flag.OPTIONAL
	ID = AttributeID.MP_UNREACH_NLRI
	MULTIPLE = True

	def __init__ (self,routes):
		self.routes = routes

	def pack (self,addpath):
		return self._attribute(self.routes[0].nlri.afi.pack() + self.routes[0].nlri.safi.pack() + ''.join([route.nlri.pack(addpath) for route in self.routes]))

	def __len__ (self):
		return len(self.pack())

	def __str__ (self):
		return "MP_UNREACH_NLRI Family %s %d NLRI(s)" % (Address.__str__(self.routes[0]),len(self.routes))
