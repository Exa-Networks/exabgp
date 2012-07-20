# encoding: utf-8
"""
eor.py

Created by Thomas Mangin on 2010-01-16.
Copyright (c) 2010-2012 Exa Networks. All rights reserved.
"""

from exabgp.protocol.ip.address import Address,AFI,SAFI
from exabgp.bgp.message.update import Update
from exabgp.bgp.message.update.attribute import Flag,Attribute
from exabgp.bgp.message.update.attribute.attributes import Attributes

# =================================================================== End-Of-Record


class EOR (Attribute):
	def __init__ (self):
		self.families = []

	def new (self,families):
		self.families = families
		return self

	def announce (self):
		r = []
		for afi,safi in self.families:
			r.append(self.mp(afi,safi))
		return r

	def mp (self,afi,safi):
		return '\x00\x00\x00\x07\x90\x0f\x00\x03' + afi.pack() + safi.pack()

	def __str__ (self):
		return 'EOR %s' % ', '.join(['%s %s' % (str(afi),str(safi)) for (afi,safi) in self.families])
