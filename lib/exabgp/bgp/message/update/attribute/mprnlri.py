# encoding: utf-8
"""
mprnlri.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2013 Exa Networks. All rights reserved.
"""

from exabgp.bgp.message.update.attribute.id import AttributeID
from exabgp.bgp.message.update.attribute import Flag,Attribute

# =================================================================== MP Unreacheable NLRI (15)

class MPRNLRI (Attribute):
	FLAG = Flag.OPTIONAL
	ID = AttributeID.MP_REACH_NLRI
	MULTIPLE = True

	def __init__ (self,nlris):
		# all the routes must have the same next-hop
		self.nlris = nlris


	def packed_attributes (self,addpath):
		if not self.nlris:
			return

		mpnlri = {}
		for nlri in self.nlris:
			if nlri.nexthop:
				# .packed and not .pack()
				# we do not want a next_hop attribute packed (with the _attribute()) but just the next_hop itself
				if nlri.safi.has_rd():
					nexthop = chr(0)*8 + nlri.nexthop.packed
				else:
					nexthop = nlri.nexthop.packed
			else:
				# EOR fo not and Flow may not have any next_hop
				nexthop = ''

			# mpunli[afi,safi][nexthop] = nlri
			mpnlri.setdefault((nlri.afi.pack(),nlri.safi.pack()),{}).setdefault(nexthop,[]).append(nlri.pack(addpath))

		for (pafi,psafi),data in mpnlri.iteritems():
			for nexthop,nlris in data.iteritems():
				yield self._attribute(
					pafi + psafi +
					chr(len(nexthop)) + nexthop +
					chr(0) + ''.join(nlris)
				)

	def pack (self,addpath):
		return ''.join(self.packed_attributes(addpath))

	def __len__ (self):
		return len(self.pack())

	def __str__ (self):
		return "MP_REACH_NLRI %d NLRI(s)" % len(self.nlris)
