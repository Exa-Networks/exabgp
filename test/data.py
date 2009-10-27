#!/usr/bin/env python
# encoding: utf-8
"""
data.py

Created by Thomas Mangin on 2009-09-06.
Copyright (c) 2009 Exa Networks. All rights reserved.
"""

import unittest

from bgp.data import *

class TestData (unittest.TestCase):
	def test_1_ip (self):
		self.assertEqual(IP('1.2.3.4'),(1<<24)+(2<<16)+(3<<8)+4)
	def test_2_ip (self):
		self.assertEqual(str(IP((1<<24)+(2<<16)+(3<<8)+4)),'1.2.3.4')
	def test_3_ip (self):
		self.failUnlessRaises(ValueError,IP,'A')
	def test_4_ip (self):
		self.assertEqual(str(IP('::ffff:192.168.1.26')),'::ffff:192.168.1.26')
	def test_5_ip (self):
		self.failUnlessRaises(ValueError,IP,"2001:0000:1234:G:0000:C1C0:ABCD:0876")

	def test_1_mask (self):
		mask = Mask(24,32)
	def test_2_mask (self):
		mask = Mask(64,128)
	# Plenty of tests missing here

	def test_1_prefix (self):
		self.assertEqual(Prefix('10.0.0.0','24'),(4, 167772160, 24))
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
		self.assertEqual(Community('0x100'),256)
	def test_3_community (self):
		self.assertEqual(Community('1:1'),65537)
	def test_4_community (self):
		self.assertEqual(Community('1:1').pack(),''.join([chr(c) for c in  [0x0,0x1,0x0,0x1]]))

if __name__ == '__main__':
	unittest.main()

