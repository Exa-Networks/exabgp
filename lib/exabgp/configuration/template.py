# encoding: utf-8
"""
parse_family.py

Created by Thomas Mangin on 2015-06-16.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

from exabgp.configuration.core import Section
from exabgp.configuration.neighbor import ParseNeighbor


class ParseTemplate (Section):
	syntax = \
		'template <name> {\n' \
		'   <neighbor commands>\n' \
		'}'

	known = ParseNeighbor.known
	action = ParseNeighbor.action
	default = ParseNeighbor.default

	name = 'template'

	def __init__ (self, tokeniser, scope, error, logger):
		Section.__init__(self,tokeniser,scope,error,logger)

	def clear (self):
		self._names = []

	def pre (self):
		named = self.tokeniser.line[1]
		self.check_name(named)
		self.scope.enter(named)
		self.scope.to_context()
		return True

	def post (self):
		self.scope.leave()
		return True
