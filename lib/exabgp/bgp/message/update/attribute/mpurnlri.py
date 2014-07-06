# encoding: utf-8
"""
mprnlri.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2013 Exa Networks. All rights reserved.
"""

from struct import unpack

from exabgp.bgp.message.update.attribute.attribute import Attribute
from exabgp.bgp.message.update.attribute.flag import Flag
from exabgp.bgp.message.update.attribute.id import AttributeID
from exabgp.bgp.message.update.nlri.nlri import NLRI
from exabgp.bgp.message.direction import IN

from exabgp.bgp.message.notification import Notify


# ================================================================= MP NLRI (14)

class MPURNLRI (Attribute):
	FLAG = Flag.OPTIONAL
	ID = AttributeID.MP_UNREACH_NLRI
	MULTIPLE = True

	__slots__ = ['nlris']

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

	@classmethod
	def unpack (cls,data,negotiated):
		nlris = []

		# -- Reading AFI/SAFI
		afi,safi = unpack('!HB',data[:3])
		offset = 3
		data = data[offset:]

		if (afi,safi) not in negotiated.families:
			raise Notify(3,0,'presented a non-negotiated family %d/%d' % (afi,safi))

		if not data:
			raise Notify(3,0,'tried to withdraw an EOR for family %d/%d' % (afi,safi))

		# Is the peer going to send us some Path Information with the route (AddPath)
		addpath = negotiated.addpath.receive(afi,safi)

		while data:
			length,nlri = NLRI.unpack(afi,safi,data,addpath,None,IN.withdrawn)
			nlris.append(nlri)
			data = data[length:]
			#logger.parser(LazyFormat("parsed withdraw mp nlri %s payload " % nlri,od,data[:length]))

		return MPURNLRI(nlris)

MPURNLRI.register_attribute()

EMPTY_MPURNLRI = MPURNLRI([])
