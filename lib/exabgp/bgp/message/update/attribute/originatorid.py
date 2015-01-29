# encoding: utf-8
"""
originatorid.py

Created by Thomas Mangin on 2012-07-07.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

from exabgp.protocol.ip import IPv4

from exabgp.bgp.message.update.attribute.attribute import Attribute


# ============================================================== OriginatorID (3)

class OriginatorID (Attribute,IPv4):
	ID = Attribute.CODE.ORIGINATOR_ID
	FLAG = Attribute.Flag.OPTIONAL
	CACHING = True

	__slots__ = []

	def pack (self, negotiated=None):
		return self._attribute(self.packed)

	@classmethod
	def unpack (cls, data, negotiated):
		return IPv4.unpack(data,cls)
