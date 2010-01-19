#!/usr/bin/env python
# encoding: utf-8
"""
route.py

Created by Thomas Mangin on 2010-01-16.
Copyright (c) 2010 Exa Networks. All rights reserved.
"""

from bgp.structure.afi import AFI
from bgp.structure.safi import SAFI
from bgp.structure.ip import to_Prefix,to_IP
from bgp.structure.nlri import NLRI

from bgp.message.update import Update,NLRIS

from bgp.message.update.attributes import Attributes
from bgp.message.update.attribute import Attribute

from bgp.message.update.attribute.nexthop     import to_NextHop
from bgp.message.update.attribute.mprnlri     import MPRNLRI
from bgp.message.update.attribute.mpurnlri    import MPURNLRI

# This class must be separated from the wire representation of a Route
# =================================================================== Route

def to_Route (ip,netmask):
	prefix = to_Prefix(ip,netmask)
	return Route(prefix.afi,prefix.safi,prefix)

class Route (NLRI,Attributes):
	def __init__ (self,afi,safi,nlri):
		NLRI.__init__(self,afi,safi,nlri)
		Attributes.__init__(self)

	def update (self):
		if self.afi == AFI.ipv4:
			return Update(NLRIS(),NLRIS([self.nlri]),self)
		if self.afi == AFI.ipv6:
			return Update(NLRIS(),NLRIS(),self)

	def pack (self):
		return NLRI.pack(self)

	def __str__ (self):
		return "%s%s" % (NLRI.__str__(self),Attributes.__str__(self))

