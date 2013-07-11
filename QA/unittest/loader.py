#!/usr/bin/env python
# encoding: utf-8
"""
table.py

Created by Thomas Mangin on 2009-08-25.
Copyright (c) 2009-2013 Exa Networks. All rights reserved.
"""

import os
import glob
import unittest

from exabgp.configuration.environment import environment
env = environment.setup('')

from exabgp.configuration.loader import read
#from exabgp.configuration.loader import InvalidFormat

class TestLoader (unittest.TestCase):

	def setUp(self):
		self.folder = os.path.abspath(os.path.join(os.path.abspath(__file__),'..','..','configuration'))

	def test_loader (self):
		for exaname in glob.glob('%s/*.exa' % self.folder):
			jsonname = '%s.json' % exaname[:-4]
			exa = read(exaname)
			jsn = read(jsonname)
			if not exa or not jsn:
				self.fail('parsing of %s or %s did not return a valid dictionary' % (exaname,jsonname))

			# import json
			# print json.dumps(exa, sort_keys=True,indent=3,separators=(',', ': '))
			# print

			if exa != jsn:
				self.fail('parsing of %s and/or %s did not return the expect result' % (exaname,jsonname))

if __name__ == '__main__':
	unittest.main()
