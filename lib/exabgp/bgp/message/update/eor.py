# encoding: utf-8
"""
eor.py

Created by Thomas Mangin on 2010-01-16.
Copyright (c) 2009-2013  Exa Networks. All rights reserved.
"""
from struct import unpack

from exabgp.bgp.message import Message
from exabgp.bgp.message.direction import IN,OUT
from exabgp.bgp.message.update.nlri.eor import NLRIEOR
from exabgp.bgp.message.update.attributes import Attributes

# =================================================================== End-Of-RIB
# not technically a different message type but easier to treat as one

def _short (data):
	return unpack('!H',data[:2])[0]

class EOR (Message):
	TYPE = chr(0x02)  # it is an update
	PREFIX = '\x00\x00\x00\x07\x90\x0f\x00\x03'

	def __init__ (self,afi,safi,action=OUT.announce):
		self.nlris = [NLRIEOR(afi,safi,action),]
		self.attributes = Attributes()

	def message (self):
		return self._message(
			self.PREFIX + self.nlris[0].pack()
		)

	def __str__ (self):
		return 'EOR'

def EORFactory (data):
	afi  = _short(data[-3:-1])
	safi = ord(data[-1])
	return EOR(afi,safi,IN.announced)
