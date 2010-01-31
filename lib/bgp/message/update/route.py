#!/usr/bin/env python
# encoding: utf-8
"""
route.py

Created by Thomas Mangin on 2010-01-16.
Copyright (c) 2010 Exa Networks. All rights reserved.
"""

from bgp.structure.address import AFI,Address
from bgp.structure.ip import to_Prefix

from bgp.message.update.attributes import Attributes
from bgp.message.update import Update,NLRIS

# This class must be separated from the wire representation of a Route
# =================================================================== Route

class Route (Address,Attributes):
	def __init__ (self,afi,safi,nlri):
		Address.__init__(self,afi,safi)
		Attributes.__init__(self)
		self.nlri = nlri

	def update (self):
		if self.afi == AFI.ipv4:
			return Update(NLRIS(),NLRIS([self.nlri]),self)
		if self.afi == AFI.ipv6:
			return Update(NLRIS(),NLRIS(),self)

	def __str__ (self):
		return "%s %s%s" % (Address.__str__(self),str(self.nlri),Attributes.__str__(self))

