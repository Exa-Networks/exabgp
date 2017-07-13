# encoding: utf-8
"""
announce/label.py

Created by Thomas Mangin on 2017-07-05.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from exabgp.protocol.ip import NoNextHop

from exabgp.rib.change import Change

from exabgp.bgp.message import OUT

from exabgp.protocol.family import AFI
from exabgp.protocol.family import SAFI

from exabgp.bgp.message.update.nlri.inet import INET
from exabgp.bgp.message.update.nlri.cidr import CIDR
from exabgp.bgp.message.update.attribute import Attributes

from exabgp.configuration.announce import ParseAnnounce
from exabgp.configuration.announce.ip import AnnounceIP

from exabgp.configuration.static.parser import prefix
from exabgp.configuration.static.parser import path_information


class AnnouncePath (ParseAnnounce):
	# put next-hop first as it is a requirement atm
	definition = [
		'label <15 bits number>',
	] + AnnounceIP.definition

	syntax = \
		'<safi> <ip>/<netmask> { ' \
		'\n   ' + ' ;\n   '.join(definition) + '\n}'

	known = dict(AnnounceIP.known,**{
		'path-information':    path_information,
	})

	action = dict(AnnounceIP.action,**{
		'path-information':    'nlri-set',
	})

	assign = dict(AnnounceIP.assign,**{
		'path-information':    'path_info',
	})

	name = 'path'
	afi = None

	def __init__ (self, tokeniser, scope, error, logger):
		ParseAnnounce.__init__(self,tokeniser,scope,error,logger)

	def clear (self):
		return True

	def _check (self):
		if not self.check(self.scope.get(self.name),self.afi):
			return self.error.set(self.syntax)
		return True

	@staticmethod
	def check (change,afi):
		if change.nlri.nexthop is NoNextHop \
			and change.nlri.action == OUT.ANNOUNCE \
			and change.nlri.afi == afi \
			and change.nlri.safi in (SAFI.unicast,SAFI.multicast):
			return False
		return True


def ip_unicast (tokeniser,afi,safi):
	ipmask = prefix(tokeniser)

	nlri = INET(afi,safi,OUT.ANNOUNCE)
	nlri.cidr = CIDR(ipmask.pack(),ipmask.mask)

	change = Change(
		nlri,
		Attributes()
	)

	while True:
		command = tokeniser()

		if not command:
			break

		action = AnnouncePath.action.get(command,'')

		if action == 'attribute-add':
			change.attributes.add(AnnouncePath.known[command](tokeniser))
		elif action == 'nlri-set':
			change.nlri.assign(AnnouncePath.assign[command],AnnouncePath.known[command](tokeniser))
		elif action == 'nexthop-and-attribute':
			nexthop,attribute = AnnouncePath.known[command](tokeniser)
			change.nlri.nexthop = nexthop
			change.attributes.add(attribute)
		else:
			raise ValueError('route: unknown command "%s"' % command)

	return [change]


@ParseAnnounce.register('unicast','extend-name','ipv4')
def unicast_v4 (tokeniser):
	return ip_unicast(tokeniser,AFI.ipv4,SAFI.unicast)


@ParseAnnounce.register('unicast','extend-name','ipv6')
def unicast_v6 (tokeniser):
	return ip_unicast(tokeniser,AFI.ipv6,SAFI.unicast)
