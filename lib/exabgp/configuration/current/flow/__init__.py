# encoding: utf-8
"""
parse_flow.py

Created by Thomas Mangin on 2015-06-04.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

from exabgp.configuration.current.core import Section

from exabgp.configuration.current.flow.route import ParseFlowRoute
from exabgp.configuration.current.flow.route import ParseFlowMatch
from exabgp.configuration.current.flow.route import ParseFlowThen


class ParseFlow (Section):
	syntax = \
		'flow {\n' \
		'  %s' \
		'}' % ';\n  '.join(ParseFlowRoute.syntax.split('\n'))

	name = 'flow'

	def __init__ (self, tokeniser, scope, error, logger):
		Section.__init__(self,tokeniser,scope,error,logger)

	# def clear (self):
	# 	self.state = 'out'

	def pre (self):
		return True

	def post (self):
		return True

	def _check (self):
		return True
