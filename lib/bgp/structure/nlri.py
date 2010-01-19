#!/usr/bin/env python
# encoding: utf-8
"""
address.py

Created by Thomas Mangin on 2010-01-15.
Copyright (c) 2010 Exa Networks. All rights reserved.
"""

from bgp.structure.afi  import AFI
from bgp.structure.safi import SAFI

## =================================================================== Address

class Address (object):
	def __init__ (self,afi,safi):
		self.afi = AFI(afi)
		self.safi = SAFI(safi)

# =================================================================== List of NLRI

class NLRIS (list):
	def __str__ (self):
		return "NLRIS %s" % str([str(nlri) for nlri in self])

