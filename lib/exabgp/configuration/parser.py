# encoding: utf-8
"""
configuration.py

Created by Thomas Mangin on 2009-08-25.
Copyright (c) 2009-2013 Exa Networks. All rights reserved.
"""

from exabgp.configuration.io.reader import Reader
from exabgp.configuration.io.parser import tokens,parser

from exabgp.configuration.registry import Registry

# required to register the callbacks
from exabgp.configuration.family import Family

class Parser (object):
	def __init__ (self,fname,text=False):
		#self.debug = environment.settings().debug.configuration
		#self.logger = Logger()
		self._text = text
		self._fname = fname

	def reload (self):
		registry = Registry()

		with Reader(self._fname) as r:
			tokeniser = tokens(r)
			registry.handle(lambda : parser(tokeniser))


Parser('/Users/thomas/source/git/exabgp/master/dev/family.txt').reload()
