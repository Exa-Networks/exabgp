#!/usr/bin/env python
# encoding: utf-8
"""
eor.py

Created by Thomas Mangin on 2012-07-20.
Copyright (c) 2009-2013 Exa Networks. All rights reserved.
"""

from exabgp.protocol.ip.address import Address

class NLRIEOR (Address):
	nexthop = None

	def __init__ (self,afi,safi,action):
		Address.__init__(self,afi,safi)
		self.attributes = None  # API compatibility with Route
		self.action = action

	def pack (self):
		return self.afi.pack() + self.safi.pack()

	def __str__ (self):
		return self.extensive()

	def extensive (self):
		return '%s eor %d/%d (%s %s)' % (self.action,self.afi,self.safi,self.afi,self.safi)
