# encoding: utf-8
"""
parse_family.py

Created by Thomas Mangin on 2015-06-16.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

from string import ascii_letters
from string import digits

from exabgp.configuration.current.generic import Generic
from exabgp.configuration.current.neighbor import ParseNeighbor


class ParseTemplate (Generic):
	syntax = \
		'syntax:\n' \
		'template <name> {\n' \
		'   <neighbor commands>\n' \
		'}\n'

	known = ParseNeighbor.known
	add = ParseNeighbor.add
	append = ParseNeighbor.append
	default = ParseNeighbor.default

	name = 'template'

	def __init__ (self, tokeniser, scope, error, logger):
		Generic.__init__(self,tokeniser,scope,error,logger)
		self._templates = []

	def clear (self):
		pass

	def pre (self):
		name = self.tokeniser.line[1]
		if name in self._templates:
			raise ValueError('this template name already exists')
		self._templates.append(name)

		if any(False if c in ascii_letters + digits + '.-_' else True for c in name):
			raise ValueError('invalid character in template name')

		self.scope.enter(name)
		self.scope.to_context()
		return True

	def post (self):
		self.scope.leave()
		return True
