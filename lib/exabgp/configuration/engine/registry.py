# encoding: utf-8
"""
registry.py

Created by Thomas Mangin on 2014-06-22.
Copyright (c) 2014-2014 Exa Networks. All rights reserved.
"""

from collections import defaultdict

from exabgp.configuration.engine.tokeniser import UnexpectedData


# ===================================================================== dictdict
# an Hardcoded defaultdict with dict as method

class dictdict (defaultdict):
	def __init__ (self):
		self.default_factory = dict


# ======================================================================= Raised
# To replace Fxception, and give line etc.

class Raised (UnexpectedData):
	syntax = ''

	def __init__ (self,tokeniser,message,syntax=''):
		super(Raised,self).__init__(
			tokeniser.idx_line,
			tokeniser.idx_position,
			tokeniser.line,
			message
		)
		# allow to give the right syntax in using Raised
		if syntax:
			self.syntax = syntax

	def __str__ (self):
		return '\n\n'.join((
			UnexpectedData.__str__(self),
			'syntax:\n%s' % self.syntax if self.syntax else '',
		))

# ======================================================================== Entry
# The common function all Section should have

class Entry (object):
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
		token = tokeniser()
		if token != '{': raise Raised(tokeniser,'was expecting {',self.syntax)

	def unamed_exit (self,tokeniser):
		# no verification to do
		pass

# ===================================================================== Registry
# The class where all configuration callback are registered to

class Registry (object):
	def __init__ (self):
		self.stack = []
		self._klass = {}
		self._handler = {}

	# self.location set by Registry

	def register (self,cls,location):
		cls.register(self,location)

	def register_class (self,cls):
		print "class %s registered" % cls.__name__
		if not cls in self._klass:
			self._klass[cls] = cls()

	def register_hook (self,cls,action,position,function):
		key = '/'.join(position)
		if action in self._handler:
			raise Exception('conflicting handlers')
		self._handler.setdefault(key,{})[action] = getattr(cls,function)
		print "%-35s %-7s %s.%-20s registered" % (key if key else 'root',action,cls.__name__,function)

	def handle (self,tokeniser):
		# each section can registered named configuration for reference here
		Entry.configuration[tokeniser.name] = defaultdict(dictdict)

		def run (search,section,location):
			key = '/'.join(search)
			function = self._handler.get(key,{}).get(section,None)

			if function:
				print 'hit %s/%s' % (key,section)
				instance = self._klass.setdefault(function.im_class,function.im_class())
				instance.location = location
				return function(instance,tokeniser) is None
			return False

		while True:
			token = tokeniser()
			if not token: break

			if run(self.stack + [token,],'enter',self.stack):
				self.stack.append(token)
				continue

			if run(self.stack+[token,],'action',self.stack+[token]):
				continue

			if token != '}':
				# we need the line and position at this level
				raise Raised(tokeniser,'invalid configuration location /%s/%s' % ('/'.join(self.stack),token))

			if run(self.stack,'exit',self.stack[:-1]):
				self.stack.pop()
				continue

			# we need the line and position at this level
			raise Exception('application error, no exit code registered for %s, please report with your configuration' % '/'.join(self.stack))
