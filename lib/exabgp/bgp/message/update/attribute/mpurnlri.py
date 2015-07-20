# encoding: utf-8
"""
mprnlri.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

from struct import unpack

from exabgp.protocol.family import AFI
from exabgp.protocol.family import SAFI
from exabgp.protocol.family import Family

from exabgp.bgp.message.direction import IN
from exabgp.bgp.message.update.attribute.attribute import Attribute
from exabgp.bgp.message.update.nlri import NLRI

from exabgp.bgp.message.notification import Notify


# ================================================================= MP NLRI (14)

@Attribute.register()
class MPURNLRI (Attribute,Family):
	FLAG = Attribute.Flag.OPTIONAL
	ID = Attribute.CODE.MP_UNREACH_NLRI

	# __slots__ = ['nlris']

	def __init__ (self, afi, safi, nlris):
		Family.__init__(self,afi,safi)
		self.nlris = nlris

	def __eq__ (self, other):
		return \
			self.ID == other.ID and \
			self.FLAG == other.FLAG and \
			self.nlris == other.nlris

	def __ne__ (self, other):
		return not self.__eq__(other)

	def packed_attributes (self, negotiated):
		if not self.nlris:
			return

		# we changed the API to nrli.pack from addpath to negotiated but not pack itself
		maximum = negotiated.FREE_SIZE

		mpurnlri = {}
		for nlri in self.nlris:
			mpurnlri.setdefault((nlri.afi.pack(),nlri.safi.pack()),[]).append(nlri.pack(negotiated))

		for (pafi,psafi),nlris in mpurnlri.iteritems():
			payload = pafi + psafi + ''.join(nlris)

			if self._len(payload) <= maximum:
				yield self._attribute(payload)
				continue

			# This will not generate an optimum update size..
			# we should feedback the maximum on each iteration

			for nlri in nlris:
				yield self._attribute(pafi + psafi + nlri)

	def pack (self, negotiated):
		return ''.join(self.packed_attributes(negotiated))

	def __len__ (self):
		raise RuntimeError('we can not give you the size of an MPURNLRI - was it with our witout addpath ?')

	def __repr__ (self):
		return "MP_UNREACH_NLRI for %s %s with %d NLRI(s)" % (self.afi,self.safi,len(self.nlris))

	@classmethod
	def unpack (cls, data, negotiated):
		nlris = []

		# -- Reading AFI/SAFI
		afi,safi = unpack('!HB',data[:3])
		offset = 3
		data = data[offset:]

		if negotiated and (afi,safi) not in negotiated.families:
			raise Notify(3,0,'presented a non-negotiated family %s %s' % (AFI(afi),SAFI(safi)))

		# Is the peer going to send us some Path Information with the route (AddPath)
		addpath = negotiated.addpath.receive(afi,safi)

		while data:
			nlri,data = NLRI.unpack_nlri(afi,safi,data,IN.WITHDRAWN,addpath)
			nlris.append(nlri)

		return cls(afi,safi,nlris)

EMPTY_MPURNLRI = MPURNLRI(AFI(AFI.undefined),SAFI(SAFI.undefined),[])
