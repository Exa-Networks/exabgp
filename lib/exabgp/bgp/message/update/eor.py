# encoding: utf-8
"""
eor.py

Created by Thomas Mangin on 2010-01-16.
Copyright (c) 2009-2013  Exa Networks. All rights reserved.
"""
from struct import unpack

from exabgp.protocol.family import AFI,SAFI
from exabgp.bgp.message import Message
from exabgp.bgp.message.direction import IN,OUT
from exabgp.bgp.message.update.attribute import Attributes
from exabgp.bgp.message.update.nlri.nlri import NLRI

# =================================================================== End-Of-RIB
# not technically a different message type but easier to treat as one


class EOR (Message):
	TYPE = chr(0x02)  # it is an update

	class NLRI (NLRI):
		PREFIX = '\x00\x00\x00\x07\x90\x0f\x00\x03'

		nexthop = None

		def __init__ (self,afi,safi,action):
			NLRI.__init__(self,afi,safi)
			self.action = action


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

	def __init__ (self,afi,safi,action=OUT.announce):
		self.nlris = [EOR.NLRI(afi,safi,action),]
		self.attributes = Attributes()

	def message (self):
		return self._message(
			self.nlris[0].pack()
		)

	def __str__ (self):
		return 'EOR'

	# default IPv4 unicast
	@classmethod
	def unpack (cls,data='\x00\x01\x01'):
		afi,  = unpack('!H',data[-3:-1])
		safi = ord(data[-1])
		return cls(afi,safi,IN.announced)
