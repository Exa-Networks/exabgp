#!/usr/bin/env python
# encoding: utf-8
"""
update.py

Created by Thomas Mangin on 2009-09-06.
Copyright (c) 2009 Exa Networks. All rights reserved.
"""

import unittest

from bgp.message.update import *

class TestData (unittest.TestCase):
	def test_2_prefix (self):
		self.assertEqual(str(Prefix('10.0.0.0','24')),'10.0.0.0/24')
	def test_6_prefix (self):
		self.assertEqual(Prefix('1.2.3.4','0').bgp(),''.join([chr(c) for c in [0,]]))
	def test_7_prefix (self):
		self.assertEqual(Prefix('1.2.3.4','8').bgp(),''.join([chr(c) for c in [8,1,]]))
	def test_8_prefix (self):
		self.assertEqual(Prefix('1.2.3.4','16').bgp(),''.join([chr(c) for c in [16,1,2]]))
	def test_9_prefix (self):
		self.assertEqual(Prefix('1.2.3.4','24').bgp(),''.join([chr(c) for c in [24,1,2,3]]))
	def test_10_prefix (self):
		self.assertEqual(Prefix('1.2.3.4','32').bgp(),''.join([chr(c) for c in [32,1,2,3,4]]))

	def test_1_community (self):
		self.assertEqual(Community(256),256)
	def test_2_community (self):
		self.assertEqual(Community().new('0x100'),256)
	def test_3_community (self):
		self.assertEqual(Community().new('1:1'),65537)
	def test_4_community (self):
		self.assertEqual(Community().new('1:1').pack(),''.join([chr(c) for c in  [0x0,0x1,0x0,0x1]]))

if __name__ == '__main__':
	unittest.main()
