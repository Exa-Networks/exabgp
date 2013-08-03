# encoding: utf-8
"""
originatorid.py

Created by Thomas Mangin on 2012-07-07.
Copyright (c) 2009-2013 Exa Networks. All rights reserved.
"""

from exabgp.protocol.ip.inet import Inet
from exabgp.bgp.message.update.attribute.id import AttributeID
from exabgp.bgp.message.update.attribute import Flag,Attribute

# =================================================================== OriginatorID (3)

class OriginatorID (Attribute,Inet):
	ID = AttributeID.ORIGINATOR_ID
	FLAG = Flag.OPTIONAL
	MULTIPLE = False

	# Take an IP as value
	def __init__ (self,afi,safi,packed):
		Inet.__init__(self,afi,safi,packed)
		# This override Inet.pack too.
		self.packed = self._attribute(Inet.pack(self))

	def pack (self,asn4=None):
		return Inet.pack(self)

	def __str__ (self):
		return Inet.__str__(self)
