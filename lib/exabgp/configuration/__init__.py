# encoding: utf-8
"""
registry.py

Created by Thomas Mangin on 2014-06-22.
Copyright (c) 2014-2015 Exa Networks. All rights reserved.
"""

from exabgp.configuration.engine.raised import Raised
from exabgp.configuration.engine.section import Section

from exabgp.configuration.engine.reader import Reader
from exabgp.configuration.engine.tokeniser import Tokeniser

from collections import defaultdict
from exabgp.util.dictionary import Dictionary

from StringIO import StringIO
import time


# ===================================================================== Registry
# The class where all configuration callback are registered to

class Configuration (object):
	def __init__ (self):
		self.stack = []
		self._klass = {}
		self._handler = {}
		self._parser = None
		self.section = None

	# self.location set by Registry

	def register (self, cls, location):
		cls.register(self,location)

	def register_class (self, cls):
		print
		print "class %s" % cls.__name__
		print "-"*40
		if not cls in self._klass:
			self._klass[cls] = cls()
		print

	def register_hook (self, cls, action, position, function):
		key = '/'.join(position)
		if action in self._handler:
			raise Exception('conflicting handlers')
		self._handler.setdefault(key,{})[action] = getattr(cls,function)
		print "%-50s %-7s %s.%s" % (key if key else 'root',action,cls.__name__,function)

	def iterate (self, tokeniser):
		# each section can registered named configuration for reference here
		Section.configuration[tokeniser.name] = defaultdict(Dictionary)

		def run (search, section, location):
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

			location = self.stack+[token,]

			# if we have both a section and a action, try the action first
			if run(location,'action',location):
				yield None
				continue

			if run(location,'enter',self.stack):
				self.stack.append(token)
				yield None
				continue

			if token != '}':
				print
				print 'Available paths are .....'
				print
				for path in sorted(self._handler):
					for action in sorted(self._handler[path]):
						print '/%-50s %s' % (path,action)
				print '....'
				print
				print '/'.join(location)
				# we need the line and position at this level
				raise Raised(tokeniser,'no parser for the location /%s' % ('/'.join(location)))

			if run(self.stack,'exit',self.stack[:-1]):
				self.stack.pop()
				yield None
				continue

			# we need the line and position at this level
			raise Exception('application error, no exit code registered for %s, please report with your configuration' % '/'.join(self.stack))

		data = Section.configuration[tokeniser.name]
		del Section.configuration[tokeniser.name]
		yield data

	def parse_tokeniser (self, tokeniser):
		if self._parser is None:
			self._parser = self.iterate(tokeniser)

		next = self._parser.next()
		if next is None:
			return None
		self._parser = None
		return next

	def parse_file (self, fname):
		with Reader(fname) as r:
			tokeniser = Tokeniser('configuration',r)
			parsed = None
			while parsed is None:
				parsed = self.parse_tokeniser(tokeniser)
		return parsed

	def parse_string (self, string):
		name = 'command-%d' % int(int(time.time()*1000) % (365*24*60*60*1000))
		sio = StringIO(string)
		tokeniser = Tokeniser(name,sio)
		parsed = None
		while parsed is None:
			parsed = self.parse_tokeniser(tokeniser)
		return parsed
