# encoding: utf-8
"""
factory.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2013 Exa Networks. All rights reserved.
"""

from exabgp.protocol.family import AFI,SAFI

from exabgp.bgp.message import defix
from exabgp.bgp.message.direction import IN

from exabgp.bgp.message.update.attribute.id import AttributeID as AID

from exabgp.bgp.message.update import Update
from exabgp.bgp.message.update.nlri.route import Route
from exabgp.bgp.message.notification import Notify

from exabgp.bgp.message.update.nlri.factory import NLRIFactory
from exabgp.bgp.message.update.attributes.factory import AttributesFactory

def UpdateFactory (negotiated,data):
	length = len(data)

	lw,withdrawn,data = defix(data)

	if len(withdrawn) != lw:
		raise Notify(3,1,'invalid withdrawn routes length, not enough data available')

	la,attribute,announced = defix(data)

	if len(attribute) != la:
		raise Notify(3,1,'invalid total path attribute length, not enough data available')

	if 2 + lw + 2+ la + len(announced) != length:
		raise Notify(3,1,'error in BGP message lenght, not enough data for the size announced')

	attributes = AttributesFactory(NLRIFactory,negotiated,attribute)

	# Is the peer going to send us some Path Information with the route (AddPath)
	addpath = negotiated.addpath.receive(AFI(AFI.ipv4),SAFI(SAFI.unicast))
	nh = attributes.get(AID.NEXT_HOP,None)

	routes = []
	while withdrawn:
		nlri = NLRIFactory(AFI.ipv4,SAFI.unicast_multicast,withdrawn,addpath,nh,IN.withdrawn)
		route = Route(nlri,IN.withdrawn)
		route.attributes = attributes
		withdrawn = withdrawn[len(nlri):]
		routes.append(route)

	while announced:
		nlri = NLRIFactory(AFI.ipv4,SAFI.unicast_multicast,announced,addpath,nh,IN.announced)
		route = Route(nlri,IN.announced)
		route.attributes = attributes
		announced = announced[len(nlri):]
		routes.append(route)

	# next_hop_attributes = {}

	for nlri in attributes.mp_withdraw:
		routes.append(Route(nlri,IN.withdrawn))

	for nlri in attributes.mp_announce:
		# next_hop = route.attributes[AttributeID.NEXT_HOP]
		# str_hop = str(next_hop)
		# if not str_hop in next_hop_attributes:
		# 	attr = deepcopy(attributes)
		# 	attr[AttributeID.NEXT_HOP] = next_hop
		# 	next_hop_attributes[str_hop] = attr
		# route.attributes = next_hop_attributes[str_hop]
		routes.append(Route(nlri,IN.announced))

	return Update().new(routes)
