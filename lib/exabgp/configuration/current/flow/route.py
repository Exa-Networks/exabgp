# encoding: utf-8
"""
parse_flow.py

Created by Thomas Mangin on 2015-06-22.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

from exabgp.configuration.current.core import Section

# from exabgp.configuration.current.flow.parser import source


def nop ():  # XXX: DELETEME
	pass


class ParseFlowRoute (Section):
	syntax = \
		'syntax:\n' \
		'  route give-me-a-name\n' \
		'     route-distinguisher|rd 255.255.255.255:65535|65535:65536|65536:65535; (optional)\n' \
		'     next-hop 1.2.3.4; (to use with redirect-to-nexthop)\n' \
		'     match {\n' \
		'     ...\n' \
		'     }\n' \
		'     then {\n' \
		'     ...\n' \
		'     }\n' \
		'  }\n'

	known = {
		'route-distinguisher':  nop,
		'next-hop':             nop,
	}

	action = {
		'route-distinguisher': 'nlri-assign',
		'next-hop':            'nlri-nexthop',   # is this correct ?
	}

	assign = {
		'route-distinguisher': 'not-sure-the-name',  # XXX: FIXME
	}

	name = 'flow/route'

	def __init__ (self, tokeniser, scope, error, logger):
		Section.__init__(self,tokeniser,scope,error,logger)

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
