#!/usr/bin/env python
# encoding: utf-8
"""
data.py

Created by Thomas Mangin on 2009-09-06.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

import unittest

from exabgp.configuration.environment import environment
environment.setup('')

# from exabgp.protocol.family import AFI
# from exabgp.protocol.family import SAFI

class TestData (unittest.TestCase):
	def setUp (self):
		pass

	# def test_1_nlri_1 (self):
	# 	self.assertEqual(''.join([chr(c) for c in [32,1,2,3,4]]),to_NLRI('1.2.3.4','32').pack())
	# def test_1_nlri_2 (self):
	# 	self.assertEqual(''.join([chr(c) for c in [24,1,2,3]]),to_NLRI('1.2.3.4','24').pack())
	# def test_1_nlri_3 (self):
	# 	self.assertEqual(''.join([chr(c) for c in [20,1,2,3]]),to_NLRI('1.2.3.4','20').pack())
	#
	# def test_2_ip_2 (self):
	# 	self.assertEqual(str(InetIP('::ffff:192.168.1.26')),'::ffff:192.168.1.26/128')
	# 	self.assertEqual(str(InetIP('::ffff:192.168.1.26').ip),'::ffff:192.168.1.26')
	#
	# def test_3_ipv6_1 (self):
	# 	default = InetIP('::')
	# 	self.assertEqual(str(default),'::/128')
	# 	self.assertEqual(default.ip,'::')
	# 	self.assertEqual(default.packedip(),'\0'*16)
	#
	# def test_3_ipv6_2 (self):
	# 	default = InetIP('1234:5678::')
	# 	self.assertEqual(str(default),'1234:5678::/128')
	# 	self.assertEqual(default.ip,'1234:5678::')
	# 	self.assertEqual(default.packedip(),'\x12\x34\x56\x78'+'\0'*12)
	#
	# def test_3_ipv6_3 (self):
	# 	default = InetIP('1234:5678::1')
	# 	self.assertEqual(str(default),'1234:5678::1/128')
	# 	self.assertEqual(default.ip,'1234:5678::1')
	# 	self.assertEqual(default.packedip(),'\x12\x34\x56\x78'+'\0'*11 + '\x01')
	#
	# def test_xxx (self):
	# 	ip = "192.0.2.0"
	# 	net  = chr (192) + chr(0) + chr(2) +chr(0)
	# 	bnt = chr(24) + chr (192) + chr(0) + chr(2)
	#
	# 	pfx = Prefix(AFI.ipv4,ip,24)
	# 	bgp = BGPNLRI(AFI.ipv4,bnt)
	#
	# 	self.assertEqual(str(pfx),"%s/24" % ip)
	# 	self.assertEqual(str(afi),"%s/24" % ip)
	# 	self.assertEqual(str(bgp),"%s/24" % ip)
	#
	# 	self.assertEqual(pfx.pack(),bnt)
	# 	self.assertEqual(afi.pack(),bnt)
	# 	self.assertEqual(bgp.pack(),bnt)
	#
	# 	# README: NEED To add ASN test
	# 	# README: NEED To add NLRI test

if __name__ == '__main__':
	unittest.main()
