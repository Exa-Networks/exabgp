# encoding: utf-8
"""
section.py

Created by Thomas Mangin on 2014-06-22.
Copyright (c) 2014-2014 Exa Networks. All rights reserved.
"""

from exabgp.configuration.engine.registry import Raised


# ====================================================================== Section
# The common function all Section should have

class Section (object):
	configuration = dict()

	def drop_parenthesis (self,tokeniser):
		if tokeniser() != '{':
			raise Raised(tokeniser,'missing semi-colon',self.syntax)

	def create_section (self,section,tokeniser):
		name = tokeniser()
		if name == '{': raise Raised(tokeniser,'was expecting section name',self.syntax)
		self.drop_parenthesis(tokeniser)

		storage = self.configuration[tokeniser.name][section][name]
		if storage:
			raise Raised(tokeniser,'the section name %s is not unique' % name,self.syntax)
		return storage

	def get_section (self,section,tokeniser):
		name = tokeniser()

		if name == '{':
			tokeniser.rewind(name)
			return None

		storage = self.configuration[tokeniser.name][section][name]
		if storage is None:
			raise Raised(tokeniser,'the section name %s referenced does not exists' % name,self.syntax)
		return storage

	def _check_duplicate (self,tokeniser,klass):
		key = self.location[-3]
		if key in self.content:
			raise klass(tokeniser,"duplicate entries for %s" % key)

	def unamed_enter (self,tokeniser):
#		import pdb; pdb.set_trace()
		token = tokeniser()
		if token != '{': raise Raised(tokeniser,'was expecting {',self.syntax)

	def unamed_exit (self,tokeniser):
		# no verification to do
		pass
