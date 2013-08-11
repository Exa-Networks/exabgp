# encoding: utf-8
"""
mprnlri.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2013 Exa Networks. All rights reserved.
"""

from exabgp.bgp.message.update.attribute.id import AttributeID
from exabgp.bgp.message.update.attribute import Flag,Attribute

# =================================================================== MP NLRI (14)

class MPURNLRI (Attribute):
	FLAG = Flag.OPTIONAL
	ID = AttributeID.MP_UNREACH_NLRI
	MULTIPLE = True

	def __init__ (self,nlris):
		self.nlris = nlris

	def packed_attributes (self,addpath):
		if not self.nlris:
			return

		mpurnlri = {}
		for nlri in self.nlris:
			mpurnlri.setdefault((nlri.afi.pack(),nlri.safi.pack()),[]).append(nlri.pack(addpath))

		for (pafi,psafi),nlris in mpurnlri.iteritems():
			yield self._attribute(pafi + psafi + ''.join(nlris))

	def pack (self,addpath):
		return ''.join(self.packed_attributes(addpath))

	def __len__ (self):
		return len(self.pack())

	def __str__ (self):
		return "MP_UNREACH_NLRI %d NLRI(s)" % len(self.nlris)
