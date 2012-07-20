# encoding: utf-8
"""
eor.py

Created by Thomas Mangin on 2010-01-16.
Copyright (c) 2010-2012 Exa Networks. All rights reserved.
"""

from exabgp.bgp.message import Message
from exabgp.protocol.ip.address import Address

# =================================================================== End-Of-RIB
# not technically a different message type but easier to treat as one

class EOR (Message):
	TYPE = chr(0x02)

	def __init__ (self):
		self.routes = []

	def new (self,afi,safi):
		self.afi = afi
		self.safi = safi
		return self

	def pack (self):
		return self._message('\x00\x00\x00\x07\x90\x0f\x00\x03' + self.afi.pack() + self.safi.pack())

	def __str__ (self):
		return 'EOR %s %s' % (self.afi,self.safi)

class RouteEOR (object):
	def __init__ (self,afi,safi,action):
		self.nlri = Address(afi,safi)
		self.action = action

	def pack (self):
		return '\x00\x00\x00\x07\x90\x0f\x00\x03' + self.nlri.afi.pack() + self.nlri.safi.pack()

	def __str__ (self):
		return '%s eor %d/%d (%s %s)' % (self.action,self.nlri.afi,self.nlri.safi,self.nlri.afi,self.nlri.safi)
