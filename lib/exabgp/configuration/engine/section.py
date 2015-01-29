# encoding: utf-8
"""
section.py

Created by Thomas Mangin on 2014-06-22.
Copyright (c) 2014-2015 Exa Networks. All rights reserved.
"""

from exabgp.configuration.engine.raised import Raised

# ====================================================================== Section
# The common function all Section should have


class Section (object):
	configuration = dict()
	factory = dict()

	# to be defined in subclasses
	name = ''
	syntax = ''

	def __init__ (self):
		# we get our name through our subclasses
		self.factory[self.name] = self

	def drop_parenthesis (self, tokeniser):
		if tokeniser() != '{':
			# syntax is set in our subclasses
			raise Raised(tokeniser,'missing opening parenthesis "{"',self.syntax)

	def create_section (self, section, tokeniser):
		name = tokeniser()
		if name == '{':
			# syntax is set in our subclasses
			raise Raised(tokeniser,'was expecting section name',self.syntax)
		self.drop_parenthesis(tokeniser)
		return self.create_content(section,name,tokeniser)

	def create_content (self, section, name, tokeniser):
		storage = self.configuration[tokeniser.name][section][name]
		if storage:
			# syntax is set in our subclasses
			raise Raised(tokeniser,'the section name %s/%s for %s is not unique' % (section,name,tokeniser.name),self.syntax)
		return storage

	def get_section (self, section, tokeniser):
		name = tokeniser()

		if name == '{':
			tokeniser.rewind(name)
			tokeniser.rewind('anonymous')
			return None

		storage = self.configuration[tokeniser.name][section][name]
		if storage is None:
			# syntax is set in our subclasses
			raise Raised(tokeniser,'the section name %s referenced does not exists' % name,self.syntax)
		return storage

	def extract_anonymous (self, section, tokeniser):
		if 'anonymous' in self.configuration[tokeniser.name][section]:
			storage = self.configuration[tokeniser.name][section]['anonymous']
			del self.configuration[tokeniser.name][section]['anonymous']
			return storage
		else:
			return None

	def _check_duplicate (self, tokeniser, klass):
		# location is set by our caller
		key = self.location[-3]  # pylint: disable=E1101
		if key in self.content:
			raise klass(tokeniser,"duplicate entries for %s" % key)

	# default function for entering and exiting

	def enter (self, tokeniser):
		self.content = self.create_section(self.name,tokeniser)

	def exit (self, tokeniser):
		# no verification to do
		pass

	def enter_nameless (self, tokeniser):
		token = tokeniser()
		if token != '{':
			# syntax is set in our subclasses
			raise Raised(tokeniser,'was expecting {',self.syntax)

	def exit_nameless (self, tokeniser):
		# no verification to do
		pass

	def enter_anonymous (self, tokeniser):
		token = tokeniser()
		if token != '{':
			# syntax is set in our subclasses
			raise Raised(tokeniser,'was expecting {',self.syntax)
		self.content = self.create_content(self.name,'anonymous',tokeniser)

	def exit_anonymous (self, tokeniser):
		# no verification to do
		pass
