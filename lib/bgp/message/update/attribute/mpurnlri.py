#!/usr/bin/env python
# encoding: utf-8
"""
mprnlri.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009 Exa Networks. All rights reserved.
"""

from bgp.utils import *
from bgp.structure.nlri import Address
from bgp.message.update.attribute import AttributeID,Flag,PathAttribute

# =================================================================== MP NLRI (14)

class MPURNLRI (Address,PathAttribute):
	FLAG = Flag.OPTIONAL
	ID = AttributeID.MP_UNREACH_NLRI  
	MULTIPLE = True

	def __init__ (self,afi,safi,nlri):
		Address.__init__(self,afi,safi)
		PathAttribute.__init__(self,nlri)

	def pack (self):
		return self._attribute(self.afi.pack() + self.safi.pack() + self.attribute.pack())

	def __len__ (self):
		return len(self.pack())

	def __str__ (self):
		return "MP Unreacheable NLRI"
