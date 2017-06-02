# encoding: utf-8
"""
announce/__init__.py

Created by Thomas Mangin on 2015-06-04.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
"""

from exabgp.configuration.core import Section


class ParseAnnounce (Section):
	name = 'announce'

	def __init__ (self, tokeniser, scope, error, logger):
		Section.__init__(self,tokeniser,scope,error,logger)

	def clear (self):
		return True

	def pre (self):
		self.scope.to_context()
		return True

	def post (self):
		routes = self.scope.pop('routes',[])
		self.scope.pop()
		self.scope.to_context()
		if routes:
			self.scope.extend('routes',routes)
		self.scope.pop(self.name)
		return True
