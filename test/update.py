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
		self.assertEqual(str(to_NLRI('10.0.0.0','24')),'10.0.0.0/24')
	def test_6_prefix (self):
		self.assertEqual(to_NLRI('1.2.3.4','0').pack(),''.join([chr(c) for c in [0,]]))
	def test_7_prefix (self):
		self.assertEqual(to_NLRI('1.2.3.4','8').pack(),''.join([chr(c) for c in [8,1,]]))
	def test_8_prefix (self):
		self.assertEqual(to_NLRI('1.2.3.4','16').pack(),''.join([chr(c) for c in [16,1,2]]))
	def test_9_prefix (self):
		self.assertEqual(to_NLRI('1.2.3.4','24').pack(),''.join([chr(c) for c in [24,1,2,3]]))
	def test_10_prefix (self):
		self.assertEqual(to_NLRI('1.2.3.4','32').pack(),''.join([chr(c) for c in [32,1,2,3,4]]))

	def test_1_community (self):
		self.assertEqual(Community(256),256)
	def test_2_community (self):
		self.assertEqual(to_Community('0x100'),256)
	def test_3_community (self):
		self.assertEqual(to_Community('1:1'),65537)
	def test_4_community (self):
		communities = Communities()
		community = to_Community('1:1')
		communities.add(community)
		self.assertEqual(communities.pack(),''.join([chr(c) for c in [0xc0,0x08,0x04,0x00,0x01,0x00,0x01]]))

if __name__ == '__main__':
	unittest.main()
