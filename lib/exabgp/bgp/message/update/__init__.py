# encoding: utf-8
"""
update/__init__.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2013 Exa Networks. All rights reserved.
"""

from exabgp.protocol.family import AFI,SAFI
from exabgp.bgp.message import Message,prefix

from exabgp.bgp.message.update.attribute.mprnlri import MPRNLRI
from exabgp.bgp.message.update.attribute.mpurnlri import MPURNLRI


# =================================================================== Update

class Update (Message):
	TYPE = chr(0x02)

	def new (self,routes):
		if routes:
			self.afi = routes[0].nlri.afi
			self.safi = routes[0].nlri.safi
			self.attributes = routes[0].attributes
		self.routes = routes
		return self

	# The routes MUST have the same attributes ...
	def announce (self,negotiated):
		asn4 = negotiated.asn4
		local_as = negotiated.local_as
		peer_as = negotiated.peer_as
		addpath = negotiated.addpath
		msg_size = negotiated.msg_size
		addpath = negotiated.addpath.send(self.afi,self.safi)

		if self.afi == AFI.ipv4 and self.safi in [SAFI.unicast, SAFI.multicast]:
			nlri = ''.join([route.nlri.pack(addpath) for route in self.routes if route.nlri.family() in negotiated.families])
			mp = ''
		else:
			nlri = ''
			if self.routes[0].nlri.family() in negotiated.families:
				mp = MPRNLRI(self.routes).pack(addpath)
			else:
				mp = ''

		if not nlri and not mp:
			return ''

		attr = self.attributes.pack(asn4,local_as,peer_as)
		packed = self._message(prefix('') + prefix(attr + mp) + nlri)
		if len(packed) > msg_size:
			routes = self.routes
			left = self.routes[:len(self.routes)/2]
			right = self.routes[len(self.routes)/2:]
			packed = []
			self.routes = left
			packed.extend(self.announce(negotiated))
			self.routes = right
			packed.extend(self.announce(negotiated))
			self.routes = routes
			return packed
		return [packed]


	def withdraw (self,negotiated=None):
		if negotiated:
			#asn4 = negotiated.asn4
			#local_as = negotiated.local_as
			#peer_as = negotiated.peer_as
			addpath = negotiated.addpath.send(self.afi,self.safi)
			msg_size = negotiated.msg_size
		else:
			#asn4 = False
			#local_as = None
			#peer_as = None
			addpath = False
			msg_size = 4077

		if self.afi == AFI.ipv4 and self.safi in [SAFI.unicast, SAFI.multicast]:
			nlri = ''.join([route.nlri.pack(addpath) for route in self.routes])
			mp = ''
		else:
			nlri = ''
			mp = MPURNLRI(self.routes).pack(addpath)
		# last sentence of RFC 4760 Section 4, no attributes are required (and make sense)
		packed = self._message(prefix(nlri) + prefix(mp))
		if len(packed) > msg_size:
			routes = self.routes
			left = self.routes[:len(self.routes)/2]
			right = self.routes[len(self.routes)/2:]
			packed = []
			self.routes = left
			packed.extend(self.withdraw(negotiated))
			self.routes = right
			packed.extend(self.withdraw(negotiated))
			self.routes = routes
			return packed
		return [packed]
