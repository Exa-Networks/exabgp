# encoding: utf-8
"""
inet/__init__.py

Created by Thomas Mangin on 2015-06-04.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

from exabgp.configuration.current.static.route import ParseRoute
from exabgp.configuration.current.static.parser import prefix

from exabgp.protocol.ip import IP

from exabgp.bgp.message import OUT
from exabgp.bgp.message.update.nlri import INET
from exabgp.bgp.message.update.nlri import MPLS

from exabgp.bgp.message.update.attribute import Attributes

from exabgp.rib.change import Change


class ParseStatic (ParseRoute):
	syntax = \
		'syntax:\n' \
		'route <ip>/<netmask> ' \
		' '.join(ParseRoute.definition) + ' ;\n'

	action = dict(ParseRoute.action)
	action['route'] = 'append'

	name = 'static'

	def __init__ (self, tokeniser, scope, error, logger):
		ParseRoute.__init__(self,tokeniser,scope,error,logger)

	def pre (self):
		self.scope.to_context()
		return True

	def post (self):
		routes = self.scope.pop(self.name)
		if routes:
			self.scope.extend('routes',routes)
		return True

@ParseStatic.register('route')
def route (tokeniser):
	ipmask = prefix(tokeniser)

	# May be wrong but taken from previous code
	if 'rd' in tokeniser.tokens:
		klass = MPLS
	elif 'route-distinguisher' in tokeniser.tokens:
		klass = MPLS
	elif 'label' in tokeniser.tokens:
		# XXX: Is it right ?
		klass = MPLS
	else:
		klass = INET

	# family = {
	# 	'static-route': {
	# 		'rd': SAFI.mpls_vpn,
	# 		'route-distinguisher': SAFI.mpls_vpn,
	# 	},
	# 	'l2vpn-vpls': {
	# 		'rd': SAFI.vpls,
	# 		'route-distinguisher': SAFI.vpls,
	# 	},
	# 	'flow-route': {
	# 		'rd': SAFI.flow_vpn,
	# 		'route-distinguisher': SAFI.flow_vpn,
	# 	}
	# }

	change = Change(
		klass(
			IP.toafi(ipmask.ip),
			IP.tosafi(ipmask.ip),
			ipmask.packed,
			ipmask.mask,
			'',
			OUT.ANNOUNCE,
			None
		),
		Attributes()
	)

	while True:
		command = tokeniser()

		if not command:
			break

		if 'add' in ParseStatic.action[command]:
			change.add(ParseStatic.known[command](tokeniser))
		else:
			raise ValueError('route: unknown command "%s"' % command)

	return change
