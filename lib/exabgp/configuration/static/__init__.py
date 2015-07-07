# encoding: utf-8
"""
inet/__init__.py

Created by Thomas Mangin on 2015-06-04.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

from exabgp.configuration.static.route import ParseStaticRoute
from exabgp.configuration.static.parser import prefix

from exabgp.protocol.ip import IP
from exabgp.protocol.family import SAFI

from exabgp.bgp.message import OUT
from exabgp.bgp.message.update.nlri import INET
from exabgp.bgp.message.update.nlri import MPLS

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
		self.scope.to_context()
		return True

	def post (self):
		routes = self.scope.pop(self.name,[])
		if routes:
			self.scope.extend('routes',routes)
		return True


@ParseStatic.register('route','extend-name')
def route (tokeniser):
	ipmask = prefix(tokeniser)

	if 'rd' in tokeniser.tokens or 'route-distinguisher' in tokeniser.tokens:
		klass = MPLS
		safi = SAFI(SAFI.mpls_vpn)
	elif 'label' in tokeniser.tokens:
		# XXX: should we create a LABEL class ?
		klass = MPLS
		safi = SAFI(SAFI.nlri_mpls)
	else:
		klass = INET
		safi = IP.tosafi(ipmask.string)

	change = Change(
		klass(
			IP.toafi(ipmask.string),
			safi,
			ipmask.pack(),
			ipmask.mask,
			'',
			OUT.UNSET
		),
		Attributes()
	)

	while True:
		command = tokeniser()

		if not command:
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

	return list(ParseStatic.split(change))
