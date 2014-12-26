# encoding: utf-8
"""
parser.py

Created by Thomas Mangin on 2009-08-25.
Copyright (c) 2009-2013 Exa Networks. All rights reserved.
"""

import unittest

from exabgp.configuration.engine.reader import Reader
from exabgp.configuration.engine.tokeniser import Tokeniser
from exabgp.configuration.engine.registry import Registry

from exabgp.configuration.bgp import SectionBGP
from exabgp.configuration.bmp import SectionBMP
from exabgp.configuration.bgp.family import SectionFamily
from exabgp.configuration.bgp.capability import SectionCapability
from exabgp.configuration.bgp.session import SectionSession
from exabgp.configuration.bgp.process import SectionProcess
from exabgp.configuration.bgp.neighbor import SectionNeighbor

import pprint
pp = pprint.PrettyPrinter(indent=3)


class TestNewConfiguration (unittest.TestCase):
	def test_parsing (self):

		class Parser (object):
			def __init__ (self,fname,text=False):
				#self.debug = environment.settings().debug.configuration
				#self.logger = Logger()
				self._text = text
				self._fname = fname

			def reload (self):
				registry = Registry()
				registry.register(SectionBGP,        ['bgp'])
				registry.register(SectionFamily,     ['bgp','family'])
				registry.register(SectionCapability, ['bgp','capability'])
				registry.register(SectionSession,    ['bgp','session'])
				registry.register(SectionProcess,    ['bgp','process'])
				registry.register(SectionNeighbor,   ['bgp','neighbor'])

				registry.register(SectionBMP,        ['bmp'])

				with Reader(self._fname) as r:
					tokeniser = Tokeniser('configuration',r)
					registry.handle(tokeniser)

				return registry

		try:
			registry = Parser('./qa/new/simple.conf').reload()
		except IOError:
			registry = Parser('../new/simple.conf').reload()

		for section in ['capability','process','session','neighbor']:
			d = SectionBGP.configuration['configuration'][section]
			for k,v in d.items():
				print '%s %s ' % (section,k)
				pp.pprint(v)
				print
			print

		# print
		# for klass in sorted(registry._klass):
		# 	print '%-20s' % str(klass).split('.')[-1][:-2], registry._klass[klass].content

if __name__ == '__main__':
    unittest.main()
