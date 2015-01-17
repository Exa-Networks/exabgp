# encoding: utf-8
"""
parser.py

Created by Thomas Mangin on 2009-08-25.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
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

		def parse (fname):
			registry = Registry()
			registry.register(SectionBGP,        ['bgp'])
			registry.register(SectionFamily,     ['bgp','family'])
			registry.register(SectionCapability, ['bgp','capability'])
			registry.register(SectionSession,    ['bgp','session'])
			registry.register(SectionProcess,    ['bgp','process'])
			registry.register(SectionNeighbor,   ['bgp','neighbor'])

			registry.register(SectionBMP,        ['bmp'])

			with Reader(fname) as r:
				tokeniser = Tokeniser('configuration',r)
				parsed = None
				while parsed is None:
					parsed = registry.parse(tokeniser)

			return parsed

		try:
			parsed = parse('./qa/new/simple.conf')
		except IOError:
			parsed = parse('../new/simple.conf')

		for section in ['capability','process','session','neighbor']:
			d = parsed[section]
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
