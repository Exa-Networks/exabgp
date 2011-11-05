#!/usr/bin/env python
# encoding: utf-8
"""
route.py

Created by Thomas Mangin on 2010-01-16.
Copyright (c) 2010-2011 Exa Networks. All rights reserved.
"""

from bgp.structure.address import Address
from bgp.message.update.attributes import Attributes

# This class must be separated from the wire representation of a Route
# =================================================================== Route

class Route (object):
	def __init__ (self,nlri):
		self.nlri = nlri
		self.address = Address(nlri.afi,nlri.safi)
		self.attributes = Attributes()

	def __str__ (self):
		return "%s %s%s" % (str(self.address),str(self.nlri),str(self.attributes))

	def __repr__ (self):
		return str(self)
	
	def __eq__ (self,other):
		return str(self) == str(other)

class ReceivedRoute (Route):
	def __init__ (self,afi,safi,nlri,action):
		self.action = action	# announce or withdraw
		Route.__init__(self,afi,safi,nlri)

	def __str__ (self):
		return "%s %s" % (self.action,Route.__str__(self))
