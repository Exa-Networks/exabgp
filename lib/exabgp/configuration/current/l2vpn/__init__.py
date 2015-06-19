# encoding: utf-8
"""
l2vpn/__init__.py

Created by Thomas Mangin on 2015-06-04.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

from exabgp.configuration.current.l2vpn.vpls import ParseVPLS

# from exabgp.protocol.family import AFI
# from exabgp.protocol.family import SAFI
# from exabgp.bgp.message import OUT

from exabgp.bgp.message.update.nlri import VPLS
from exabgp.bgp.message.update.attribute import Attributes
from exabgp.rib.change import Change

from exabgp.configuration.current.l2vpn.parser import vpls


class ParseL2VPN (ParseVPLS):
	syntax = \
		'syntax:\n' \
		'vpls ' \
		' '.join(ParseVPLS.definition) + ' ;\n'

	# known = dict((k,v) for (k,v) in ParseVPLS.known.items())

	name = 'l2vpn'

	action = dict(ParseVPLS.action)
	action['vpls'] = ['append']

	def __init__ (self, tokeniser, scope, error, logger):
		ParseVPLS.__init__(self,tokeniser,scope,error,logger)

	def pre (self):
		self.scope.to_context()
		return True

	def post (self):
		routes = self.scope.pop_last(self.name)
		if routes:
			self.scope.extend('routes',routes)
		return True

	def clear (self):
		pass


@ParseL2VPN.register('vpls')
def vpls (tokeniser):
	change = Change(
		VPLS(None,None,None,None,None),
		Attributes()
	)

	while True:
		try:
			command = tokeniser()
		except StopIteration:
			break

		action = ParseVPLS.action[command]

		if 'assign' in action:
			change.nlri.assign(ParseVPLS.assign[command],ParseL2VPN.known[command](tokeniser))
		elif 'add' in action:
			change.add(ParseL2VPN.known[command](tokeniser))
		else:
			raise ValueError('vpls: unknown command "%s"' % command)

	return change
