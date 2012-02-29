# encoding: utf-8
"""
route.py

Created by Thomas Mangin on 2010-01-16.
Copyright (c) 2010-2012 Exa Networks. All rights reserved.
"""

from exabgp.structure.address import Address
from exabgp.message.update.attributes import Attributes

# This class must be separated from the wire representation of a Route
# =================================================================== Route

class Route (object):
	def __init__ (self,nlri):
		self.nlri = nlri
		self.__address = Address(nlri.afi,nlri.safi)
		self.attributes = Attributes()

	def __str__ (self):
		return "%s %s%s" % (str(self.__address),str(self.nlri),str(self.attributes))

	def __repr__ (self):
		return str(self)

	def __eq__ (self,other):
		return str(self) == str(other)

class ReceivedRoute (Route):
	def __init__ (self,nlri,action):
		self.action = action	# announce or withdraw
		Route.__init__(self,nlri)

	def __str__ (self):
		return "%s %s" % (self.action,Route.__str__(self))
