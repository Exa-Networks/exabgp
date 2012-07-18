# encoding: utf-8
"""
update/__init__.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2012 Exa Networks. All rights reserved.
"""

from exabgp.protocol.family import AFI,SAFI
from exabgp.bgp.message import Message,prefix,defix

from exabgp.bgp.message.update.attribute.mprnlri import MPRNLRI
from exabgp.bgp.message.update.attribute.mpurnlri import MPURNLRI
from exabgp.bgp.message.update.attribute.attributes import Attributes
from exabgp.bgp.message.update.nlri import routeFactory
from exabgp.bgp.message.update.nlri import RouteBGP,BGPNLRI
from exabgp.bgp.message.notification import Notify

# =================================================================== Update

class Update (Message):
	TYPE = chr(0x02)

	def new (self,routes):
		self.routes = routes
		self.afi = routes[0].nlri.afi
		self.safi = routes[0].nlri.safi
		return self

	# The routes MUST have the same attributes ...
	def announce (self,asn4,local_asn,remote_asn,with_path_info):
		if self.afi == AFI.ipv4 and self.safi in [SAFI.unicast, SAFI.multicast]:
			nlri = ''.join([route.nlri.pack(with_path_info) for route in self.routes])
			mp = ''
		else:
			nlri = ''
			mp = MPRNLRI(self.routes).pack(with_path_info)
		attr = self.routes[0].attributes.bgp_announce(asn4,local_asn,remote_asn)
		return self._message(prefix('') + prefix(attr + mp) + nlri)

	def update (self,asn4,local_asn,remote_asn,with_path_info):
		if self.afi == AFI.ipv4 and self.safi in [SAFI.unicast, SAFI.multicast]:
			nlri = ''.join([route.nlri.pack(with_path_info) for route in self.routes])
			mp = ''
		else:
			nlri = ''
			mp = MPURNLRI(self.routes).pack(with_path_info) + MPRNLRI(self.routes).pack(with_path_info)
		attr = self.routes[0].attributes.bgp_announce(asn4,local_asn,remote_asn)
		return self._message(prefix(nlri) + prefix(attr + mp) + nlri)

	# XXX: Remove those default values ? - most likely good.
	def withdraw (self,asn4=False,local_asn=None,remote_asn=None,with_path_info=None):
		if self.afi == AFI.ipv4 and self.safi in [SAFI.unicast, SAFI.multicast]:
			nlri = ''.join([route.nlri.pack(with_path_info) for route in self.routes])
			mp = ''
			attr = ''
		else:
			nlri = ''
			mp = MPURNLRI(self.routes).pack(with_path_info)
			attr = self.routes[0].attributes.bgp_announce(asn4,local_asn,remote_asn)
		return self._message(prefix(nlri) + prefix(attr + mp))


	def factory (self,asn4,families,use_path,data):
		length = len(data)
		# withdraw
		lw,withdrawn,data = defix(data)
		if len(withdrawn) != lw:
			raise Notify(3,1,'invalid withdrawn routes length, not enough data available')
		la,attribute,announced = defix(data)
		if len(attribute) != la:
			raise Notify(3,1,'invalid total path attribute length, not enough data available')
		# The RFC check ...
		#if lw + la + 23 > length:
		if 2 + lw + 2+ la + len(announced) != length:
			raise Notify(3,1,'error in BGP message lenght, not enough data for the size announced')

		# Is the peer going to send us some Path Information with the route (AddPath)
		path_info = use_path.receive(AFI(AFI.ipv4),SAFI(SAFI.unicast))

		attributes = Attributes()
		attributes.routeFactory = routeFactory
		attributes.factory(asn4,families,use_path,attribute)

		routes = []
		while withdrawn:
			nlri = BGPNLRI(AFI.ipv4,SAFI.unicast_multicast,withdrawn,path_info)
			route = RouteBGP(nlri,'withdrawn')
			route.attributes = attributes
			withdrawn = withdrawn[len(nlri):]
			routes.append(route)

		while announced:
			nlri = BGPNLRI(AFI.ipv4,SAFI.unicast_multicast,announced,path_info)
			route = RouteBGP(nlri,'announced')
			route.attributes = attributes
			announced = announced[len(nlri):]
			routes.append(route)

		for route in attributes.mp_withdraw:
			route.attributes = attributes
			routes.append(route)

		for route in attributes.mp_announce:
			route.attributes = attributes
			routes.append(route)
		
		return routes

	