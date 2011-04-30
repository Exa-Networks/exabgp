#!/usr/bin/env python
# encoding: utf-8
"""
update/__init__.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2011 Exa Networks. All rights reserved.
"""

from bgp.structure.address import AFI,SAFI
from bgp.message import Message,prefix

from bgp.message.update.attribute.mprnlri     import MPRNLRI
from bgp.message.update.attribute.mpurnlri    import MPURNLRI

# =================================================================== Update

#def bgp_mp (self):
#	if AttributeID.NEXT_HOP in self:
#		if self[AttributeID.NEXT_HOP].next_hop.afi != AFI.ipv4:
#			return MPRNLRI(self).pack()
#	return ''
#
#def bgp_resdraw (self):
#	if AttributeID.NEXT_HOP in self:
#		if self[AttributeID.NEXT_HOP].next_hop.afi != AFI.ipv4:
#			return MPURNLRI(self.afi,self.safi,self).pack()
#	return ''

class Update (Message):
	TYPE = chr(0x02)

	# All the route must be of the same family and have the same next-hop
	def __init__ (self,routes):
		self.routes = routes
		self.afi = routes[0].afi
		self.safi = routes[0].safi

	# The routes MUST have the same attributes ...
	def announce (self,asn4,local_asn,remote_asn):
		if self.afi == AFI.ipv4 and self.safi in [SAFI.unicast, SAFI.multicast]:
			nlri = ''.join([route.nlri.pack() for route in self.routes])
			mp = ''
		else:
			nlri = ''
			mp = MPRNLRI(self.routes).pack()
		attr = self.routes[0].bgp_announce(asn4,local_asn,remote_asn)
		return self._message(prefix('') + prefix(attr + mp) + nlri)

	def update (self,asn4,local_asn,remote_asn):
		if self.afi == AFI.ipv4 and self.safi in [SAFI.unicast, SAFI.multicast]:
			nlri = ''.join([route.nlri.pack() for route in self.routes])
			mp = ''
		else:
			nlri = ''
			mp = MPURNLRI(self.routes).pack() + MPRNLRI(self.routes).pack()
		attr = self.routes[0].bgp_announce(asn4,local_asn,remote_asn)
		return self._message(prefix(nlri) + prefix(attr + mp) + nlri)

	def withdraw (self,asn4=False,local_asn=None,remote_asn=None):
		if self.afi == AFI.ipv4 and self.safi in [SAFI.unicast, SAFI.multicast]:
			nlri = ''.join([route.nlri.pack() for route in self.routes])
			mp = ''
			attr = ''
		else:
			nlri = ''
			mp = MPURNLRI(self.routes).pack()
			attr = self.routes[0].bgp_announce(asn4,local_asn,remote_asn)
		return self._message(prefix(nlri) + prefix(attr + mp))
