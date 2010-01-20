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

	def __init__ (self,afi,safi,nlri):
		Address.__init__(self,afi,safi)
		Attribute.__init__(self,nlri)

	def pack (self):
		next_hop = ''
		if self.attribute.has_key(AttributeID.NEXT_HOP):
			next_hop = self.attribute[AttributeID.NEXT_HOP].attribute.pack()
		return self._attribute(
			self.afi.pack() + self.safi.pack() + 
			chr(len(next_hop)) + next_hop + 
			chr(0) + self.attribute.pack()
		)

	def __len__ (self):
		return len(self.pack())

	def __str__ (self):
		return "MP Reacheable NLRI %s %s" % (Address.__str__(self),Attribute.__str__(self))
