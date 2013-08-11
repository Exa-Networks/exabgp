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

# =================================================================== End-Of-RIB
# not technically a different message type but easier to treat as one

def _short (data):
	return unpack('!H',data[:2])[0]

class EOR (Message):
	TYPE = chr(0x02)  # it is an update
	PREFIX = '\x00\x00\x00\x07\x90\x0f\x00\x03'

	def __init__ (self,data=None):
		self.nlris = [] if data is None else [NLRIEOR(_short(data[-3:-1]),ord(data[-1]),IN.announced)]
		self.attributes = ''  # XXX: FIXME: to be clean it should be Attributes()

	def new (self,families):
		for afi,safi in families:
			self.nlris.append(NLRIEOR(afi,safi,OUT.announce))
		return self

	def updates (self,negotiated):
		for eor in self.nlris:
			yield self._message(self.PREFIX + eor.pack())

	def __str__ (self):
		return 'EOR'

def EORFactory (data):
	return EOR()
