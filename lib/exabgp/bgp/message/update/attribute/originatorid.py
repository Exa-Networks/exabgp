# encoding: utf-8
"""
originatorid.py

Created by Thomas Mangin on 2012-07-07.
Copyright (c) 2009-2013 Exa Networks. All rights reserved.
"""

from exabgp.protocol.ip import IPv4

from exabgp.bgp.message.update.attribute.id import AttributeID
from exabgp.bgp.message.update.attribute import Flag,Attribute

# ============================================================== OriginatorID (3)

class OriginatorID (Attribute,IPv4):
	ID = AttributeID.ORIGINATOR_ID
	FLAG = Flag.OPTIONAL
	MULTIPLE = False
	CACHING = True

	__slots__ = []

	def pack (self,asn4=None):
		return self._attribute(self.packed)

	@classmethod
	def unpack (cls,data,negotiated):
		return IPv4.unpack(data,cls)

OriginatorID.register()
