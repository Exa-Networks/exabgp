# encoding: utf-8
"""
registry.py

Created by Thomas Mangin on 2014-06-22.
Copyright (c) 2014-2015 Exa Networks. All rights reserved.
"""

from exabgp.configuration.engine.raised import Raised
from exabgp.configuration.engine.section import Section

from collections import defaultdict
from exabgp.util.dictionary import Dictionary


# ===================================================================== Registry
# The class where all configuration callback are registered to

class Registry (object):
	def __init__ (self):
		self.stack = []
		self._klass = {}
		self._handler = {}
		self._parser = None
		self.section = None

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

	def iterate (self,tokeniser):
		# each section can registered named configuration for reference here
		Section.configuration[tokeniser.name] = defaultdict(Dictionary)

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

			# if we have both a section and a action, try the action first
			if run(self.stack+[token,],'action',self.stack+[token]):
				yield None
				continue

			if run(self.stack + [token,],'enter',self.stack):
				self.stack.append(token)
				yield None
				continue

			if token != '}':
				print
				print 'Available paths are .....'
				print
				for path in sorted(self._handler):
					for action in sorted(self._handler[path]):
						print '/%-40s %s' % (path,action)
				print '....'
				print
				print self.stack+[token,]
				# we need the line and position at this level
				raise Raised(tokeniser,'no parser for the location /%s' % ('/'.join(self.stack+[token,])))

			if run(self.stack,'exit',self.stack[:-1]):
				self.stack.pop()
				yield None
				continue

			# we need the line and position at this level
			raise Exception('application error, no exit code registered for %s, please report with your configuration' % '/'.join(self.stack))

		data = Section.configuration[tokeniser.name]
		del Section.configuration[tokeniser.name]
		yield data

	def parse (self,tokeniser):
		if self._parser is None:
			self._parser = self.iterate(tokeniser)

		next = self._parser.next()
		if next is None:
			return None
		self._parser = None
		return next
