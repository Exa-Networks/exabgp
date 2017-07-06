# encoding: utf-8
"""
announce/flow.py

Created by Thomas Mangin on 2017-07-06.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from exabgp.rib.change import Change

from exabgp.bgp.message import OUT

from exabgp.protocol.family import AFI
from exabgp.protocol.family import SAFI

from exabgp.bgp.message.update.nlri.flow import Flow
from exabgp.bgp.message.update.attribute import Attributes

from exabgp.configuration.flow.route import ParseFlowRoute
from exabgp.configuration.flow.route import ParseFlowMatch
from exabgp.configuration.flow.route import ParseFlowThen
from exabgp.configuration.flow.route import ParseFlowScope

from exabgp.configuration.announce import ParseAnnounce


class ParseFlow (ParseAnnounce):
	syntax = \
		'flow {\n' \
		'  %s' \
		'}' % ';\n  '.join(ParseFlowRoute.syntax.split('\n'))

	name = 'flow'

	known = dict(ParseFlowMatch.known,**dict(ParseFlowThen.known,**ParseFlowScope.known))

	action = dict(ParseFlowMatch.action,**dict(ParseFlowThen.action,**ParseFlowScope.action))

	assign = dict()

	def __init__ (self, tokeniser, scope, error, logger):
		ParseAnnounce.__init__(self,tokeniser,scope,error,logger)

	def clear (self):
		pass

	def pre (self):
		self.scope.to_context(self.name)
		return True

	def post (self):
		self.scope.to_context(self.name)
		self.scope.set('routes',self.scope.pop('route',{}).get('routes',[]))
		self.scope.extend('routes',self.scope.pop('flow',[]))
		return True

	def check (self):
		return True


def flow (tokeniser,afi,safi):
	change = Change(
		Flow(afi,safi,OUT.ANNOUNCE),
		Attributes()
	)

	while True:
		command = tokeniser()

		if not command:
			break

		action = ParseFlow.action[command]

		if action == 'nlri-add':
			for adding in ParseFlow.known[command](tokeniser):
				change.nlri.add(adding)
		elif action == 'attribute-add':
			change.attributes.add(ParseFlow.known[command](tokeniser))
		elif action == 'nexthop-and-attribute':
			nexthop,attribute = ParseFlow.known[command](tokeniser)
			change.nlri.nexthop = nexthop
			change.attributes.add(attribute)
		elif action == 'nop':
			pass  # yes nothing to do !
		else:
			raise ValueError('flow: unknown command "%s"' % command)

	return [change]


@ParseAnnounce.register('flow','extend-name','ipv4')
def flow_ip_v4 (tokeniser):
	return flow(tokeniser,AFI.ipv4,SAFI.flow_ip)


@ParseAnnounce.register('flow-vpn','extend-name','ipv4')
def flow_vpn_v4 (tokeniser):
	return flow(tokeniser,AFI.ipv4,SAFI.flow_vpn)


@ParseAnnounce.register('flow','extend-name','ipv6')
def flow_ip_v6 (tokeniser):
	return flow(tokeniser,AFI.ipv6,SAFI.flow_ip)


@ParseAnnounce.register('flow-vpn','extend-name','ipv6')
def flow_vpn_v6 (tokeniser):
	return flow(tokeniser,AFI.ipv6,SAFI.flow_vpn)
