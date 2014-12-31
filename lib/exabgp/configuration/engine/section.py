# encoding: utf-8
"""
section.py

Created by Thomas Mangin on 2014-06-22.
Copyright (c) 2014-2015 Exa Networks. All rights reserved.
"""

from exabgp.configuration.engine.registry import Raised

import time
import random

# ====================================================================== Section
# The common function all Section should have

class Section (object):
	configuration = dict()
	factory = dict()

	unamed = 'unamed-%s' % hash('%s%d' % (time.asctime(),random.randint(1000,9999)))

	def __init__ (self):
		self.factory[self.name] = self

	def drop_parenthesis (self,tokeniser):
		if tokeniser() != '{':
			raise Raised(tokeniser,'missing opening parenthesis "{"',self.syntax)

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
			tokeniser.rewind(self.unamed)
			return None

		storage = self.configuration[tokeniser.name][section][name]
		if storage is None:
			raise Raised(tokeniser,'the section name %s referenced does not exists' % name,self.syntax)
		return storage

	def get_unamed (self,tokeniser,section):
		if self.unamed in self.configuration[tokeniser.name][section]:
			storage = self.configuration[tokeniser.name][section][self.unamed]
			del self.configuration[tokeniser.name][section][self.unamed]
			return storage
		else:
			return None

	def _check_duplicate (self,tokeniser,klass):
		key = self.location[-3]
		if key in self.content:
			raise klass(tokeniser,"duplicate entries for %s" % key)

	# default function for entering and exiting

	def enter (self,tokeniser):
		self.content = self.create_section(self.name,tokeniser)

	def exit (self,tokeniser):
		# no verification to do
		pass

	def enter_unamed_section (self,tokeniser):
		token = tokeniser()
		if token != '{': raise Raised(tokeniser,'was expecting {',self.syntax)

	def exit_unamed_section (self,tokeniser):
		# no verification to do
		pass
