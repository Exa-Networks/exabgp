# encoding: utf-8
"""
inet/__init__.py

Created by Thomas Mangin on 2015-06-04.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from exabgp.configuration.static.route import ParseStaticRoute
from exabgp.configuration.static.parser import prefix

from exabgp.protocol.ip import IP
from exabgp.protocol.family import SAFI

from exabgp.bgp.message import OUT
from exabgp.bgp.message.update.nlri import CIDR
from exabgp.bgp.message.update.nlri import INET
from exabgp.bgp.message.update.nlri import Label
from exabgp.bgp.message.update.nlri import IPVPN

from exabgp.bgp.message.update.attribute import Attributes

from exabgp.rib.change import Change


class ParseStatic (ParseStaticRoute):
	syntax = \
		'route <ip>/<netmask> %s;' % ' '.join(ParseStaticRoute.definition)

	action = dict(ParseStaticRoute.action)

	name = 'static'

	def __init__ (self, tokeniser, scope, error, logger):
		ParseStaticRoute.__init__(self,tokeniser,scope,error,logger)

	def clear (self):
		return True

	def pre (self):
		return True

	def post (self):
		return True


@ParseStatic.register('route','append-route')
def route (tokeniser):
	ipmask = prefix(tokeniser)

	if 'rd' in tokeniser.tokens or 'route-distinguisher' in tokeniser.tokens:
		nlri = IPVPN(IP.toafi(ipmask.top()),SAFI.mpls_vpn,OUT.ANNOUNCE)
	elif 'label' in tokeniser.tokens:
		nlri = Label(IP.toafi(ipmask.top()),SAFI.nlri_mpls,OUT.ANNOUNCE)
	else:
		nlri = INET(IP.toafi(ipmask.top()),IP.tosafi(ipmask.top()),OUT.ANNOUNCE)

	nlri.cidr = CIDR(ipmask.pack(),ipmask.mask)

	change = Change(
		nlri,
		Attributes()
	)

	while True:
		command = tokeniser()

		if not command:
			break

		action = ParseStatic.action.get(command,'')

		if action == 'attribute-add':
			change.attributes.add(ParseStatic.known[command](tokeniser))
		elif action == 'nlri-set':
			change.nlri.assign(ParseStatic.assign[command],ParseStatic.known[command](tokeniser))
		elif action == 'nexthop-and-attribute':
			nexthop,attribute = ParseStatic.known[command](tokeniser)
			change.nlri.nexthop = nexthop
			change.attributes.add(attribute)
		else:
			raise ValueError('route: unknown command "%s"' % command)

	return list(ParseStatic.split(change))


@ParseStatic.register('attributes','append-route')
def attributes (tokeniser):
	ipmask = prefix(lambda: tokeniser.tokens[-1])

	if 'rd' in tokeniser.tokens or 'route-distinguisher' in tokeniser.tokens:
		nlri = IPVPN(IP.toafi(ipmask.top()),SAFI.mpls_vpn,OUT.ANNOUNCE)
	elif 'label' in tokeniser.tokens:
		nlri = Label(IP.toafi(ipmask.top()),SAFI.nlri_mpls,OUT.ANNOUNCE)
	else:
		nlri = INET(IP.toafi(ipmask.top()),IP.tosafi(ipmask.top()),OUT.ANNOUNCE)

	nlri.cidr = CIDR(ipmask.pack(),ipmask.mask)

	change = Change(
		nlri,
		Attributes()
	)

	while True:
		command = tokeniser()

		if not command:
			return []

		if command == 'nlri':
			break

		action = ParseStatic.action[command]

		if action == 'attribute-add':
			change.attributes.add(ParseStatic.known[command](tokeniser))
		elif action == 'nlri-set':
			change.nlri.assign(ParseStatic.assign[command],ParseStatic.known[command](tokeniser))
		elif action == 'nexthop-and-attribute':
			nexthop,attribute = ParseStatic.known[command](tokeniser)
			change.nlri.nexthop = nexthop
			change.attributes.add(attribute)
		else:
			raise ValueError('route: unknown command "%s"' % command)

	attributes = change.attributes
	nexthop = change.nlri.nexthop

	changes = []
	while True:
		nlri = tokeniser.peek()
		if not nlri:
			break

		ipmask = prefix(tokeniser)
		new = Change(
			change.nlri.__class__(
				change.nlri.afi,
				change.nlri.safi,
				OUT.UNSET
			),
			attributes
		)
		new.nlri.cidr = CIDR(ipmask.pack(),ipmask.mask)
		new.nlri.nexthop = nexthop
		changes.append(new)

	return changes
