# encoding: utf-8
"""
parser.py

Created by Thomas Mangin on 2009-08-25.
Copyright (c) 2009-2013 Exa Networks. All rights reserved.
"""

from exabgp.configuration.io.reader import Reader
from exabgp.configuration.io.tokeniser import Tokeniser

from exabgp.configuration.registry import Registry

# required to register the callbacks
from exabgp.configuration.family import Family
from exabgp.configuration.capability import Capability
from exabgp.configuration.process import Process
# end required

class Parser (object):
	def __init__ (self,fname,text=False):
		#self.debug = environment.settings().debug.configuration
		#self.logger = Logger()
		self._text = text
		self._fname = fname

	def reload (self):
		registry = Registry()

		with Reader(self._fname) as r:
			tokeniser = Tokeniser(r)
			registry.handle(tokeniser)

		return registry

p = Parser('/Users/thomas/source/git/exabgp/master/dev/test-new-config.txt')
registry = p.reload()

from exabgp.configuration.registry import Entry

for klass in Entry._klass:
	print klass, Entry._klass[klass].content
