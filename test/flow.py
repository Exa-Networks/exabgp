#!/usr/bin/env python
# encoding: utf-8
"""
flow.py

Created by Thomas Mangin on 2010-01-14.
Copyright (c) 2010 Exa Networks. All rights reserved.
"""

import unittest

from bgp.message.update import flow

class TestFlow (unittest.TestCase):

	def setUp(self):
		pass

	def test_source (self):
		self.policy = flow.Policy()
		self.policy.add(flow.Destination("192.0.2.0",24))
		print self.policy.pack()
		
		
		
#		self.table = Table()
#		self.table.update(routes)
#		changed = [(t,r) for (t,r) in self.table.changed(self.now) if t]
#		self.failIf(('+',routes[0]) not in changed)
#		self.failIf(('+',routes[1]) not in changed)
#		self.failIf('-' in [t for t,r in self.table.changed(self.now) if t])
#
#	def test_2_del_all_but_1 (self):
#		self.table = Table()
#
#		self.table.update(routes)
#		changed = [(t,r) for (t,r) in self.table.changed(self.now) if t]
#		self.failIf(('+',routes[0]) not in changed)
#		self.failIf(('+',routes[1]) not in changed)
#
#		self.table.update([routes[1]])
#		self.failIf(('-',routes[0]) not in [(t,r) for (t,r) in self.table.changed(self.now) if t])
#		self.failIf(('+',routes[1]) not in [(t,r) for (t,r) in self.table.changed(self.now) if t])
#		self.failIf(('-',routes[2]) not in [(t,r) for (t,r) in self.table.changed(self.now) if t])
#
#
#	def test_3_del_all (self):
#		self.table = Table()
#
#		self.table.update(routes)
#		changed = [(t,r) for (t,r) in self.table.changed(self.now) if t]
#		self.failIf(('+',routes[0]) not in changed)
#		self.failIf(('+',routes[1]) not in changed)
#
#		self.table.update([])
#		self.failIf('+' in [t for (t,r) in self.table.changed(self.now) if t])
#		self.failIf(('-',routes[0]) not in [(t,r) for (t,r) in self.table.changed(self.now) if t])
#		self.failIf(('-',routes[1]) not in [(t,r) for (t,r) in self.table.changed(self.now) if t])
#		self.failIf(('-',routes[2]) not in [(t,r) for (t,r) in self.table.changed(self.now) if t])
#
#	def test_4_multichanges (self):
#		self.table = Table()
#
#		self.table.update(routes)
#		changed = [(t,r) for (t,r) in self.table.changed(self.now) if t]
#		self.failIf(('+',routes[0]) not in changed)
#		self.failIf(('+',routes[1]) not in changed)
#
#		self.table.update([routes[1]])
#		print '-------------------------'
#		print 
#		print [(t,r) for (t,r) in self.table.changed(self.now) if t]
#		print
#		self.failIf(('-',routes[0]) not in [(t,r) for (t,r) in self.table.changed(self.now) if t])
#		self.failIf(('+',routes[1]) not in [(t,r) for (t,r) in self.table.changed(self.now) if t])
#		self.failIf(('-',routes[2]) not in [(t,r) for (t,r) in self.table.changed(self.now) if t])
#
#		self.table.update(routes)
#		changed = [(t,r) for (t,r) in self.table.changed(self.now) if t]
#		self.failIf(('+',routes[0]) not in [(t,r) for (t,r) in self.table.changed(self.now) if t])
#		self.failIf(('+',routes[1]) not in [(t,r) for (t,r) in self.table.changed(self.now) if t])
#		self.failIf(('+',routes[2]) not in [(t,r) for (t,r) in self.table.changed(self.now) if t])

if __name__ == '__main__':
	unittest.main()