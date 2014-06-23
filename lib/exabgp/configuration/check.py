# encoding: utf-8
"""
check.py

Created by Thomas Mangin on 2009-08-25.
Copyright (c) 2009-2014 Exa Networks. All rights reserved.
"""

# check to see if we can decode what we encode

import sys

from exabgp.protocol.family import known_families

from exabgp.util.od import od
from exabgp.bgp.message.update import Update
from exabgp.bgp.message.update.factory import UpdateFactory
from exabgp.bgp.message.open import Open
from exabgp.bgp.message.open.capability import Capabilities
from exabgp.bgp.message.open.capability.negotiated import Negotiated
from exabgp.bgp.message.open.capability.id import CapabilityID
from exabgp.bgp.message.notification import Notify

from exabgp.rib.change import Change
from exabgp.logger import Logger

def check (neighbor):

	logger = Logger()

	logger._parser = True

	logger.parser('\ndecoding routes in configuration')

	n = neighbor[neighbor.keys()[0]]

	path = {}
	for f in known_families():
		if n.add_path:
			path[f] = n.add_path

	capa = Capabilities().new(n,False)
	capa[CapabilityID.ADD_PATH] = path
	capa[CapabilityID.MULTIPROTOCOL_EXTENSIONS] = n.families()

	o1 = Open(4,n.local_as,str(n.local_address),capa,180)
	o2 = Open(4,n.peer_as,str(n.peer_address),capa,180)
	negotiated = Negotiated(n)
	negotiated.sent(o1)
	negotiated.received(o2)
	#grouped = False

	for nei in neighbor.keys():
		for message in neighbor[nei].rib.outgoing.updates(False):
			pass

		for change1 in neighbor[nei].rib.outgoing.sent_changes():
			str1 = change1.extensive()
			packed = list(Update([change1.nlri],change1.attributes).messages(negotiated))
			pack1 = packed[0]

			logger.parser('parsed route requires %d updates' % len(packed))
			logger.parser('update size is %d' % len(pack1))

			logger.parser('parsed route %s' % str1)
			logger.parser('parsed hex   %s' % od(pack1))

			# This does not take the BGP header - let's assume we will not break that :)
			try:
				logger.parser('')  # new line

				pack1s = pack1[19:] if pack1.startswith('\xFF'*16) else pack1
				update = UpdateFactory(negotiated,pack1s)

				change2 = Change(update.nlris[0],update.attributes)
				str2 = change2.extensive()
				pack2 = list(Update([update.nlris[0]],update.attributes).messages(negotiated))[0]

				logger.parser('recoded route %s' % str2)
				logger.parser('recoded hex   %s' % od(pack2))

				str1r = str1.replace(' med 100','').replace(' local-preference 100','').replace(' origin igp','')
				str2r = str2.replace(' med 100','').replace(' local-preference 100','').replace(' origin igp','')

				skip = False

				if str1r != str2r:
					if 'attribute [' in str1r and ' 0x00 ' in str1r:
						# we do not decode non-transitive attributes
						logger.parser('skipping string check on update with non-transitive attribute(s)')
						skip = True
					else:
						logger.parser('strings are different:')
						logger.parser('[%s]'%str1r)
						logger.parser('[%s]'%str2r)
						sys.exit(1)
				else:
						logger.parser('strings are fine')

				if skip:
					logger.parser('skipping encoding for update with non-transitive attribute(s)')
				elif pack1 != pack2:
					logger.parser('encoding are different')
					logger.parser('[%s]'%od(pack1))
					logger.parser('[%s]'%od(pack2))
					sys.exit(1)
				else:
					logger.parser('encoding is fine')
					logger.parser('----------------------------------------')

			except Notify,e:
				print 'failed due to notification'
				print str(e)
				sys.exit(1)

	import sys
	sys.exit(0)
