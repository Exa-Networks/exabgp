#!/usr/bin/env python
# encoding: utf-8
"""
eor.py

Created by Thomas Mangin on 2012-07-20.
Copyright (c) 2009-2013 Exa Networks. All rights reserved.
"""

from exabgp.protocol.family import AFI,SAFI
from exabgp.protocol.ip.address import Address

class NLRIEOR (Address):
	PREFIX = '\x00\x00\x00\x07\x90\x0f\x00\x03'

	nexthop = None

	def __init__ (self,afi,safi,action):
		Address.__init__(self,afi,safi)
		self.action = action

	def nlri (self):
		return 'eor %d/%d' % (self.afi,self.safi)

	def pack (self):
		if self.afi == AFI.ipv4 and self.safi == SAFI.unicast:
			return '\x00\x00\x00\x00'
		return self.PREFIX + self.afi.pack() + self.safi.pack()

	def __str__ (self):
		return self.extensive()

	def extensive (self):
		return 'eor %d/%d (%s %s)' % (self.afi,self.safi,self.afi,self.safi)

	def json (self):
		return '"eor": { "afi" : "%s", "safi" : "%s" }' % (self.afi,self.safi)
