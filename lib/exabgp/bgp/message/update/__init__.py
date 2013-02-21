# encoding: utf-8
"""
update/__init__.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2013 Exa Networks. All rights reserved.
"""

from copy import deepcopy

from exabgp.protocol.family import AFI,SAFI
from exabgp.bgp.message import Message,prefix,defix

from exabgp.bgp.message.update.attribute.mprnlri import MPRNLRI
from exabgp.bgp.message.update.attribute.mpurnlri import MPURNLRI
from exabgp.bgp.message.update.attribute.id import AttributeID
from exabgp.bgp.message.update.attribute.attributes import Attributes
from exabgp.bgp.message.update.nlri.route import RouteBGP,BGPNLRI,routeFactory
from exabgp.bgp.message.notification import Notify

# =================================================================== Update

class Update (Message):
	TYPE = chr(0x02)

	def new (self,routes):
		self.routes = routes
		if routes:
			self.afi = routes[0].nlri.afi
			self.safi = routes[0].nlri.safi
			self.attributes = self.routes[0].attributes
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
			nlri = ''.join([route.nlri.pack(addpath) for route in self.routes])
			mp = ''
		else:
			nlri = ''
			mp = MPRNLRI(self.routes).pack(addpath)
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


	def factory (self,negotiated,data):
		length = len(data)

		lw,withdrawn,data = defix(data)

		if len(withdrawn) != lw:
			raise Notify(3,1,'invalid withdrawn routes length, not enough data available')

		la,attribute,announced = defix(data)

		if len(attribute) != la:
			raise Notify(3,1,'invalid total path attribute length, not enough data available')

		if 2 + lw + 2+ la + len(announced) != length:
			raise Notify(3,1,'error in BGP message lenght, not enough data for the size announced')

		attributes = Attributes()
		attributes.routeFactory = routeFactory
		attributes.factory(negotiated,attribute)

		# Is the peer going to send us some Path Information with the route (AddPath)
		addpath = negotiated.addpath.receive(AFI(AFI.ipv4),SAFI(SAFI.unicast))

		routes = []
		while withdrawn:
			nlri = BGPNLRI(AFI.ipv4,SAFI.unicast_multicast,withdrawn,addpath)
			route = RouteBGP(nlri,'withdrawn')
			route.attributes = attributes
			withdrawn = withdrawn[len(nlri):]
			routes.append(route)

		while announced:
			nlri = BGPNLRI(AFI.ipv4,SAFI.unicast_multicast,announced,addpath)
			route = RouteBGP(nlri,'announced')
			route.attributes = attributes
			announced = announced[len(nlri):]
			routes.append(route)

		next_hop_attributes = {}

		for route in attributes.mp_withdraw:
			routes.append(route)

		for route in attributes.mp_announce:
			next_hop = route.attributes[AttributeID.NEXT_HOP]
			str_hop = str(next_hop)
			if not str_hop in next_hop_attributes:
				attr = deepcopy(attributes)
				attr[AttributeID.NEXT_HOP] = next_hop
				next_hop_attributes[str_hop] = attr
			route.attributes = next_hop_attributes[str_hop]
			routes.append(route)

		return self.new(routes)
