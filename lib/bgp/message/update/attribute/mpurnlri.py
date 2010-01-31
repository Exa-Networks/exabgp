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

# =================================================================== MP NLRI (14)

class MPURNLRI (Address,Attribute):
	FLAG = Flag.OPTIONAL
	ID = AttributeID.MP_UNREACH_NLRI  
	MULTIPLE = True

	def __init__ (self,afi,safi,route):
		Address.__init__(self,afi,safi)
		self.route = route

	def pack (self):
		return self._attribute(self.afi.pack() + self.safi.pack() + self.route.nlri.pack())

	def __len__ (self):
		return len(self.pack())

	def __str__ (self):
		return "MP_UNREACH_NLRI Family %s NLRI %s" % (Address.__str__(self),str(self.route))
