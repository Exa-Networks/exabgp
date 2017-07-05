# encoding: utf-8
"""
announce/vpn.py

Created by Thomas Mangin on 2017-07-05.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from exabgp.protocol.ip import NoNextHop

from exabgp.rib.change import Change

from exabgp.bgp.message import OUT

from exabgp.protocol.family import AFI
from exabgp.protocol.family import SAFI

from exabgp.bgp.message.update.nlri import IPVPN
from exabgp.bgp.message.update.nlri.cidr import CIDR
from exabgp.bgp.message.update.attribute import Attributes

from exabgp.configuration.announce.label import ParseLabel

from exabgp.configuration.static.parser import prefix
from exabgp.configuration.static.mpls import route_distinguisher


class ParseVPN (ParseLabel):
	# put next-hop first as it is a requirement atm
	definition = [
		'  (optional) rd 255.255.255.255:65535|65535:65536|65536:65535;\n',
	] + ParseLabel.definition

	syntax = \
		'<safi> <ip>/<netmask> { ' \
		'\n   ' + ' ;\n   '.join(definition) + '\n}'

	known = dict(ParseLabel.known,**{
		'rd':                   route_distinguisher,
	})

	action = dict(ParseLabel.action,**{
		'rd':                  'nlri-set',
	})

	assign = dict(ParseLabel.assign,**{
		'rd':                  'rd',
	})

	name = 'vpn'
	afi = None

	def __init__ (self, tokeniser, scope, error, logger):
		ParseLabel.__init__(self,tokeniser,scope,error,logger)

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


def ip_vpn (tokeniser,afi,safi):
	ipmask = prefix(tokeniser)

	nlri = IPVPN(afi,safi,OUT.ANNOUNCE)
	nlri.cidr = CIDR(ipmask.pack(),ipmask.mask)

	change = Change(
		nlri,
		Attributes()
	)

	while True:
		command = tokeniser()

		if not command:
			break

		action = ParseVPN.action.get(command,'')

		if action == 'attribute-add':
			change.attributes.add(ParseVPN.known[command](tokeniser))
		elif action == 'nlri-set':
			change.nlri.assign(ParseVPN.assign[command],ParseVPN.known[command](tokeniser))
		elif action == 'nexthop-and-attribute':
			nexthop,attribute = ParseVPN.known[command](tokeniser)
			change.nlri.nexthop = nexthop
			change.attributes.add(attribute)
		else:
			raise ValueError('route: unknown command "%s"' % command)

	return [change]


class ParseIPv4VPN (ParseVPN):
	name = 'ipv4'
	afi = AFI.ipv4


@ParseIPv4VPN.register('mpls-vpn','extend-name',True)
def mpls_vpn_v4 (tokeniser):
	return ip_vpn(tokeniser,AFI.ipv4,SAFI.unicast)


class ParseIPv6VPN (ParseVPN):
	name = 'ipv6'
	afi = AFI.ipv6


@ParseIPv6VPN.register('mpls-vpn','extend-name',True)
def mpls_vpn_v6 (tokeniser):
	return ip_vpn(tokeniser,AFI.ipv6,SAFI.unicast)
