#!/usr/bin/env python
# encoding: utf-8
"""
table.py

Created by Thomas Mangin on 2009-08-25.
Copyright (c) 2009-2013 Exa Networks. All rights reserved.
"""

import unittest

from exabgp.configuration.environment import environment
env = environment.setup('')

import time

from exabgp.bgp.message.update import Route
from exabgp.rib.table import Table

route1 = Update(to_NLRI('10.0.0.1','32'))
route1.next_hop = '10.0.0.254'

route2 = Update(to_NLRI('10.0.1.1','32'))
route2.next_hop = '10.0.0.254'

route3 = Update(to_NLRI('10.0.2.1','32'))
route3.next_hop = '10.0.0.254'

routes = [route1,route2,route3]
routes.sort()


class TestTable (unittest.TestCase):

	def setUp(self):
		self.now = time.time()

	def test_1_add (self):
		self.table = Table()
		self.table.update(routes)
		changed = [(t,r) for (t,r) in self.table.changed(self.now) if t]
		self.failIf(('+',routes[0]) not in changed)
		self.failIf(('+',routes[1]) not in changed)
		self.failIf('-' in [t for t,r in self.table.changed(self.now) if t])

	def test_2_del_all_but_1 (self):
		self.table = Table()

		self.table.update(routes)
		changed = [(t,r) for (t,r) in self.table.changed(self.now) if t]
		self.failIf(('+',routes[0]) not in changed)
		self.failIf(('+',routes[1]) not in changed)

		self.table.update([routes[1]])
		self.failIf(('-',routes[0]) not in [(t,r) for (t,r) in self.table.changed(self.now) if t])
		self.failIf(('+',routes[1]) not in [(t,r) for (t,r) in self.table.changed(self.now) if t])
		self.failIf(('-',routes[2]) not in [(t,r) for (t,r) in self.table.changed(self.now) if t])


	def test_3_del_all (self):
		self.table = Table()

		self.table.update(routes)
		changed = [(t,r) for (t,r) in self.table.changed(self.now) if t]
		self.failIf(('+',routes[0]) not in changed)
		self.failIf(('+',routes[1]) not in changed)

		self.table.update([])
		self.failIf('+' in [t for (t,r) in self.table.changed(self.now) if t])
		self.failIf(('-',routes[0]) not in [(t,r) for (t,r) in self.table.changed(self.now) if t])
		self.failIf(('-',routes[1]) not in [(t,r) for (t,r) in self.table.changed(self.now) if t])
		self.failIf(('-',routes[2]) not in [(t,r) for (t,r) in self.table.changed(self.now) if t])

	def test_4_multichanges (self):
		self.table = Table()

		self.table.update(routes)
		changed = [(t,r) for (t,r) in self.table.changed(self.now) if t]
		self.failIf(('+',routes[0]) not in changed)
		self.failIf(('+',routes[1]) not in changed)

		self.table.update([routes[1]])
		print '-------------------------'
		print
		print [(t,r) for (t,r) in self.table.changed(self.now) if t]
		print
		self.failIf(('-',routes[0]) not in [(t,r) for (t,r) in self.table.changed(self.now) if t])
		self.failIf(('+',routes[1]) not in [(t,r) for (t,r) in self.table.changed(self.now) if t])
		self.failIf(('-',routes[2]) not in [(t,r) for (t,r) in self.table.changed(self.now) if t])

		self.table.update(routes)
		changed = [(t,r) for (t,r) in self.table.changed(self.now) if t]
		self.failIf(('+',routes[0]) not in [(t,r) for (t,r) in self.table.changed(self.now) if t])
		self.failIf(('+',routes[1]) not in [(t,r) for (t,r) in self.table.changed(self.now) if t])
		self.failIf(('+',routes[2]) not in [(t,r) for (t,r) in self.table.changed(self.now) if t])

if __name__ == '__main__':
	unittest.main()
