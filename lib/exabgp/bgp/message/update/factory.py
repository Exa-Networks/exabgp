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
#from exabgp.bgp.message.update.nlri.route import Route
from exabgp.bgp.message.notification import Notify

from exabgp.bgp.message.update.nlri.factory import NLRIFactory
from exabgp.bgp.message.update.attributes.factory import AttributesFactory

from exabgp.util.od import od
from exabgp.logger import Logger,LazyFormat

# XXX: FIXME: this can raise ValueError. IndexError,TypeError, struct.error (unpack) = check it is well intercepted
def UpdateFactory (negotiated,data):
	logger = Logger()

	length = len(data)

	lw,withdrawn,data = defix(data)

	if len(withdrawn) != lw:
		raise Notify(3,1,'invalid withdrawn routes length, not enough data available')

	la,attribute,announced = defix(data)

	if len(attribute) != la:
		raise Notify(3,1,'invalid total path attribute length, not enough data available')

	if 2 + lw + 2+ la + len(announced) != length:
		raise Notify(3,1,'error in BGP message length, not enough data for the size announced')

	attributes = AttributesFactory(NLRIFactory,negotiated,attribute)

	# Is the peer going to send us some Path Information with the route (AddPath)
	addpath = negotiated.addpath.receive(AFI(AFI.ipv4),SAFI(SAFI.unicast))
	nho = attributes.get(AID.NEXT_HOP,None)
	nh = nho.packed if nho else None

	if not withdrawn:
		logger.parser(LazyFormat("parsed no withdraw nlri",od,''))

	nlris = []
	while withdrawn:
		length,nlri = NLRIFactory(AFI.ipv4,SAFI.unicast_multicast,withdrawn,addpath,nh,IN.withdrawn)
		logger.parser(LazyFormat("parsed withdraw nlri %s payload " % nlri,od,withdrawn[:len(nlri)]))
		withdrawn = withdrawn[length:]
		nlris.append(nlri)

	if not announced:
		logger.parser(LazyFormat("parsed no announced nlri",od,''))

	while announced:
		length,nlri = NLRIFactory(AFI.ipv4,SAFI.unicast_multicast,announced,addpath,nh,IN.announced)
		logger.parser(LazyFormat("parsed announce nlri %s payload " % nlri,od,announced[:len(nlri)]))
		announced = announced[length:]
		nlris.append(nlri)

	for nlri in attributes.mp_withdraw:
		nlris.append(nlri)

	for nlri in attributes.mp_announce:
		nlris.append(nlri)

	return Update(nlris,attributes)
