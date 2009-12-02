#!/usr/bin/env python
# encoding: utf-8
"""
mprnlri.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009 Exa Networks. All rights reserved.
"""

from bgp.utils import *
from bgp.message.update.attribute.parent import Attribute,Flag

# =================================================================== MP NLRI (14)

class MPURNLRI (Attribute):
	FLAG = Flag.OPTIONAL
	ID = Attribute.MP_UNREACH_NLRI  
	MULTIPLE = True

	# init takes a route (and not NLRI)

	def pack (self):
		return self._attribute(AFI(AFI.ipv6).pack() + SAFI(SAFI.unicast).pack() + self.value.nlri.pack())

	def __len__ (self):
		return len(self.pack())

	def __str__ (self):
		return "MP Unreacheable NLRI"
