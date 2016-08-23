# encoding: utf-8
"""
eor.py

Created by Thomas Mangin on 2010-01-16.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

# from struct import unpack

from exabgp.protocol.family import AFI
from exabgp.protocol.family import SAFI
from exabgp.bgp.message.message import Message
from exabgp.bgp.message.update.attribute import Attributes
from exabgp.bgp.message.update.nlri import NLRI as _NLRI

# =================================================================== End-Of-RIB
# not technically a different message type but easier to treat as one


class EOR (Message):
	ID = Message.CODE.UPDATE
	TYPE = chr(Message.CODE.UPDATE)

	class NLRI (_NLRI):
		PREFIX = '\x00\x00\x00\x07\x90\x0F\x00\x03'
		EOR = True

		nexthop = None

		def __init__ (self, afi, safi, action):
			_NLRI.__init__(self,afi,safi,action)
			self.action = action

		def pack (self, negotiated=None):
			if self.afi == AFI.ipv4 and self.safi == SAFI.unicast:
				return '\x00\x00\x00\x00'
			return self.PREFIX + self.afi.pack() + self.safi.pack()

		def __repr__ (self):
			return self.extensive()

		def extensive (self):
			return 'eor %ld/%ld (%s %s)' % (long(self.afi),long(self.safi),self.afi,self.safi)

		def json (self, announced=True, compact=None):
			return '"eor": { "afi" : "%s", "safi" : "%s" }' % (self.afi,self.safi)

	def __init__ (self, afi, safi, action=None):
		Message.__init__(self)
		self.nlris = [EOR.NLRI(afi,safi,action),]
		self.attributes = Attributes()

	def message (self,negotiated=None):
		return self._message(
			self.nlris[0].pack()
		)

	def __repr__ (self):
		return 'EOR'

	@classmethod
	def unpack_message (cls, data, negotiated):
		header_length = len(EOR.NLRI.PREFIX)
		return cls(AFI.unpack(data[header_length:header_length+2]),SAFI.unpack(data[header_length+2]))
