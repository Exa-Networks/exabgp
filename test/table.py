#!/usr/bin/env python
# encoding: utf-8
"""
table.py

Created by Thomas Mangin on 2009-08-25.
Copyright (c) 2009 Exa Networks. All rights reserved.
"""

import unittest
import time

from bgp.message.update import Route
from bgp.table import Table

class TestTable (unittest.TestCase):
	routes = [Route('10.0.0.1','32','10.0.0.254'),Route('10.0.1.1','32','10.0.0.254'),Route('10.0.2.1','32','10.0.0.254')]

	def setUp(self):
		self.now = time.time()

	def test_1_add (self):
		self.table = Table()
		self.table.update(self.routes)
		changed = [(t,r) for (t,r) in self.table.changed(self.now) if t]
		self.failIf(('+',self.routes[0]) not in changed)
		self.failIf(('+',self.routes[1]) not in changed)
		self.failIf('-' in [t for t,r in self.table.changed(self.now) if t])

	def test_2_del_all_but_1 (self):
		self.table = Table()

		self.table.update(self.routes)
		changed = [(t,r) for (t,r) in self.table.changed(self.now) if t]
		self.failIf(('+',self.routes[0]) not in changed)
		self.failIf(('+',self.routes[1]) not in changed)

		self.table.update([self.routes[1]])
		self.failIf(('-',self.routes[0]) not in [(t,r) for (t,r) in self.table.changed(self.now) if t])
		self.failIf(('+',self.routes[1]) not in [(t,r) for (t,r) in self.table.changed(self.now) if t])
		self.failIf(('-',self.routes[2]) not in [(t,r) for (t,r) in self.table.changed(self.now) if t])


	def test_3_del_all (self):
		self.table = Table()

		self.table.update(self.routes)
		changed = [(t,r) for (t,r) in self.table.changed(self.now) if t]
		self.failIf(('+',self.routes[0]) not in changed)
		self.failIf(('+',self.routes[1]) not in changed)

		self.table.update([])
		self.failIf('+' in [t for (t,r) in self.table.changed(self.now) if t])
		self.failIf(('-',self.routes[0]) not in [(t,r) for (t,r) in self.table.changed(self.now) if t])
		self.failIf(('-',self.routes[1]) not in [(t,r) for (t,r) in self.table.changed(self.now) if t])
		self.failIf(('-',self.routes[2]) not in [(t,r) for (t,r) in self.table.changed(self.now) if t])

	def test_4_multichanges (self):
		self.table = Table()

		self.table.update(self.routes)
		changed = [(t,r) for (t,r) in self.table.changed(self.now) if t]
		self.failIf(('+',self.routes[0]) not in changed)
		self.failIf(('+',self.routes[1]) not in changed)

		self.table.update([self.routes[1]])
		print '-------------------------'
		print 
		print [(t,r) for (t,r) in self.table.changed(self.now) if t]
		print
		self.failIf(('-',self.routes[0]) not in [(t,r) for (t,r) in self.table.changed(self.now) if t])
		self.failIf(('+',self.routes[1]) not in [(t,r) for (t,r) in self.table.changed(self.now) if t])
		self.failIf(('-',self.routes[2]) not in [(t,r) for (t,r) in self.table.changed(self.now) if t])

		self.table.update(self.routes)
		changed = [(t,r) for (t,r) in self.table.changed(self.now) if t]
		self.failIf(('+',self.routes[0]) not in [(t,r) for (t,r) in self.table.changed(self.now) if t])
		self.failIf(('+',self.routes[1]) not in [(t,r) for (t,r) in self.table.changed(self.now) if t])
		self.failIf(('+',self.routes[2]) not in [(t,r) for (t,r) in self.table.changed(self.now) if t])

if __name__ == '__main__':
	unittest.main()