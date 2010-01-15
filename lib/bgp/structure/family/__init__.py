#!/usr/bin/env python
# encoding: utf-8
"""
__init__.py

Created by Thomas Mangin on 2010-01-15.
Copyright (c) 2010 Exa Networks. All rights reserved.
"""

from bgp.structure.family.afi import AFI
from bgp.structure.family.safi import SAFI

## =================================================================== Family
#
#class Family (object):
#	def __init__ (self,afi,safi):
#		self.afi = AFI(afi)
#		self.safi = SAFI(safi)
#
#	def format (self):
#		if afi in (AFI.ipv4,AFI.ipv6) and safi in (SAFI.unicast,): return NLRI
