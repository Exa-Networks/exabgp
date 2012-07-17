# encoding: utf-8
"""
route.py

Created by Thomas Mangin on 2010-01-16.
Copyright (c) 2010-2012 Exa Networks. All rights reserved.
"""

from exabgp.protocol.ip.address import Address
from exabgp.bgp.message.update.attribute.attributes import Attributes

# This class must be separated from the wire representation of a Route
# =================================================================== Route

class Route (object):
	def __init__ (self,nlri):
		self.nlri = nlri
		self.__address = Address(nlri.afi,nlri.safi)
		self.attributes = Attributes()

	def __str__ (self):
		return "route %s%s" % (str(self.nlri),str(self.attributes))

	def extensive (self):
		return "%s %s%s" % (str(self.__address),str(self.nlri),str(self.attributes))

	def index (self):
		return self.nlri.packed+self.nlri.rd.rd

class RouteBGP (Route):
	def __init__ (self,nlri,action):
		self.action = action	# announce, announced, withdraw or withdrawn
		Route.__init__(self,nlri)

	def __str__ (self):
		return "%s %s" % (self.action,Route.__str__(self))
