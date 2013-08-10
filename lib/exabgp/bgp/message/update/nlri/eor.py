#!/usr/bin/env python
# encoding: utf-8
"""
eor.py

Created by Thomas Mangin on 2012-07-20.
Copyright (c) 2009-2013 Exa Networks. All rights reserved.
"""

from struct import unpack
from exabgp.bgp.message.direction import IN
from exabgp.protocol.ip.address import Address

class FakeNLRI (Address):
	nexthop = None

	def __init__ (self,afi,safi,action):
		self.action = action
		Address.__init__(self,afi,safi)

class RouteEOR (object):
	PREFIX = '\x00\x00\x00\x07\x90\x0f\x00\x03'

	def __init__ (self,afi,safi,action):
		self.nlri = FakeNLRI(afi,safi,action)
		self.attributes = None  # API compatibility with Route

	def pack (self):
		return self.PREFIX + self.nlri.afi.pack() + self.nlri.safi.pack()

	def __str__ (self):
		return self.extensive()

	def extensive (self):
		return '%s eor %d/%d (%s %s)' % (self.action,self.nlri.afi,self.nlri.safi,self.nlri.afi,self.nlri.safi)

def announcedRouteEOR (data):
	return RouteEOR(unpack('!H',data[-4:-2])[0],unpack('!H',data[-2:])[0],IN.announced)
