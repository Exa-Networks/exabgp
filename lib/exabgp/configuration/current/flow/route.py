# encoding: utf-8
"""
parse_flow.py

Created by Thomas Mangin on 2015-06-22.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

from exabgp.configuration.current.core import Section

from exabgp.configuration.current.flow.match import ParseFlowMatch
from exabgp.configuration.current.flow.then import ParseFlowThen

from exabgp.configuration.current.static.mpls import route_distinguisher
from exabgp.configuration.current.static.parser import next_hop

from exabgp.configuration.current.flow.parser import flow


class ParseFlowRoute (Section):
	syntax = \
		'route give-me-a-name {\n' \
		'  (optional) route-distinguisher|rd 255.255.255.255:65535|65535:65536|65536:65535;\n' \
		'  next-hop 1.2.3.4; (to use with redirect-to-nexthop)\n' \
		'  %s\n' \
		'  %s\n' \
		'}\n' % (
			'\n  '.join(ParseFlowMatch.syntax.split('\n')),
			'\n  '.join(ParseFlowThen.syntax.split('\n'))
		)

	known = {
		'rd':                   route_distinguisher,
		'route-distinguisher':  route_distinguisher,
		'next-hop':             next_hop,
	}

	action = {
		'rd':                  'nlri-set',
		'route-distinguisher': 'nlri-set',
		'next-hop':            'nlri-nexthop',
	}

	assign = {
		'rd':                  'rd',
		'route-distinguisher': 'rd',
	}

	name = 'flow/route'

	def __init__ (self, tokeniser, scope, error, logger):
		Section.__init__(self,tokeniser,scope,error,logger)

	def pre (self):
		self.scope.set(self.name,flow(self.tokeniser.iterate))
		return True

	def post (self):
		if not self._check():
			return False
		# self.scope.to_context()
		route = self.scope.pop(self.name)
		if route:
			self.scope.append('routes',route)
		return True

	def _check (self):
		self.logger.configuration('warning: no check on flows are implemented')
		return True
