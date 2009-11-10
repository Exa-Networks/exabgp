#!/usr/bin/env python
# encoding: utf-8
"""
data.py

Created by Thomas Mangin on 2009-09-06.
Copyright (c) 2009 Exa Networks. All rights reserved.
"""

import unittest

from bgp.message.inet import *
from bgp.message.update import new_Updates

class TestData (unittest.TestCase):
#	def test_1_ip (self):
#		self.assertEqual(IP('1.2.3.4'),(1<<24)+(2<<16)+(3<<8)+4)
#	def test_2_ip (self):
#		self.assertEqual(str(IP((1<<24)+(2<<16)+(3<<8)+4)),'1.2.3.4')
	def test_3_ip (self):
		self.failUnlessRaises(ValueError,IPv4,'A')
	def test_4_ip (self):
		self.assertEqual(str(IPv6('::ffff:192.168.1.26')),'::ffff:192.168.1.26')
	def test_5_ip (self):
		self.failUnlessRaises(ValueError,IPv6,"2001:0000:1234:G:0000:C1C0:ABCD:0876")

	def test_1_nlri (self):
		self.assertEqual(''.join([chr(c) for c in [32,1,2,3,4]]),to_NLRI('1.2.3.4','32').pack())
	def test_2_nlri (self):
		self.assertEqual(''.join([chr(c) for c in [24,1,2,3]]),to_NLRI('1.2.3.4','24').pack())
	def test_3_nlri (self):
		self.assertEqual(''.join([chr(c) for c in [20,1,2,3]]),to_NLRI('1.2.3.4','20').pack())

	def test_1_ipv6 (self):
		default = IPv6('::')
		self.assertEqual(str(default),'::')
		self.assertEqual(default.pack(),'\0'*16)

	def test_2_ipv6 (self):
		default = IPv6('1234:5678::')
		self.assertEqual(str(default),'1234:5678::')
		self.assertEqual(default.pack(),'\x12\x34\x56\x78'+'\0'*12)

	def test_3_ipv6 (self):
		default = IPv6('1234:5678::1')
		self.assertEqual(str(default),'1234:5678::1')
		self.assertEqual(default.pack(),'\x12\x34\x56\x78'+'\0'*11 + '\x01')


# XXX: NEED To add ASN test
# XXX: NEED To add NLRI test

if __name__ == '__main__':
	unittest.main()

