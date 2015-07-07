# encoding: utf-8
"""
generic/__init__.py

Created by Thomas Mangin on 2015-06-04.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

from string import ascii_letters
from string import digits

from exabgp.configuration.core.error import Error


class Section (Error):
	name = 'undefined'
	known = dict()     # command/section and code to handle it
	default = dict()   # command/section has a a defult value, use it if no data was provided
	action = {}        # how to handle this command ( append, add, assign, route )
	assign = {}        # configuration to class variable lookup for setattr

	def __init__ (self, tokerniser, scope, error, logger):
		Error.__init__(self)
		self.tokeniser = tokerniser
		self.scope = scope
		self.error = error
		self.logger = logger
		self._names = []

	def clear (self):
		raise RuntimeError('%s did not implemented clear as should be' % self.__class__.__name__)

	@classmethod
	def register (cls, name, action):
		def inner (function):
			if name in cls.known:
				raise RuntimeError('more than one registration per command attempted')
			cls.known[name] = function
			cls.action[name] = action
			return function
		return inner

	def check_name (self, name):
		if any(False if c in ascii_letters + digits + '.-_' else True for c in name):
			self.throw('invalid character in name for %s ' % self.name)
		if name in self._names:
			self.throw('the name "%s" already exists in %s' % (name,self.name))
		self._names.append(name)

	def pre (self):
		return True

	def post (self):
		return True

	def parse (self, name, command):
		if command not in self.known:
			return self.error.set('unknown command %s options are %s' % (command,', '.join(self.known)))

		try:
			if command in self.default:
				insert = self.known[command](self.tokeniser.iterate,self.default[command])
			else:
				insert = self.known[command](self.tokeniser.iterate)

			action = self.action[command]

			if action == 'set-command':
				self.scope.set(command,insert)
			elif action == 'extend-name':
				self.scope.extend(name,insert)
			elif action == 'append-name':
				self.scope.append(name,insert)
			elif action == 'append-command':
				self.scope.append(command,insert)
			elif action == 'attribute-add':
				self.scope.attribute_add(name,insert)
			elif action == 'nlri-set':
				self.scope.nlri_assign(name,self.assign[command],insert)
			elif action == 'nlri-add':
				for adding in insert:
					self.scope.nlri_add(name,command,adding)
			elif action == 'nlri-nexthop':
				self.scope.nlri_nexthop(name,insert)
			elif action == 'nexthop-and-attribute':
				ip, attribute = insert
				if ip:
					self.scope.nlri_nexthop(name,ip)
				if attribute:
					self.scope.attribute_add(name,attribute)
			elif action == 'nop':
				pass
			else:
				raise RuntimeError('name %s command %s has no action set' % (name,command))
			return True
		except ValueError, exc:
			return self.error.set(str(exc))

		return True
