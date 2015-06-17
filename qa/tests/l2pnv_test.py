#!/usr/bin/env python
# encoding: utf-8
"""
l2vpn.py

Created by Thomas Mangin on 2010-01-14.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

import unittest

from exabgp.bgp.message.update.nlri import VPLS
from exabgp.bgp.message.update.nlri.qualifier import RouteDistinguisher


class TestL2VPN (unittest.TestCase):
	@staticmethod
	def generate_rd (rd):
		"""only ip:num is supported atm.code from configure.file"""
		separator = rd.find(':')
		prefix = rd[:separator]
		suffix = int(rd[separator+1:])
		data = [chr(0),chr(1)]
		data.extend([chr(int(_)) for _ in prefix.split('.')])
		data.extend([chr(suffix >> 8),chr(suffix & 0xFF)])
		bin_rd = ''.join(data)
		return RouteDistinguisher(bin_rd)

	def setUp (self):
		"""
		setUp unittesting

		l2vpn:endpoint:3:base:262145:offset:1:size:8: route-distinguisher 172.30.5.4:13
		l2vpn:endpoint:3:base:262145:offset:1:size:8: route-distinguisher 172.30.5.3:11
		"""
		self.encoded_l2vpn_nlri1 = bytearray.fromhex(u'0011 0001 AC1E 0504 000D 0003 0001 0008 4000 11')
		self.encoded_l2vpn_nlri2 = bytearray.fromhex(u'0011 0001 AC1E 0503 000B 0003 0001 0008 4000 11')
		self.decoded_l2vpn_nlri1 = VPLS(TestL2VPN.generate_rd('172.30.5.4:13'),3,262145,1,8)
		self.decoded_l2vpn_nlri2 = VPLS(TestL2VPN.generate_rd('172.30.5.3:11'),3,262145,1,8)
		"""
		output from Juniper
		Communities: target:54591:6 Layer2-info: encaps: VPLS, control flags:[0x0] , mtu: 0, site preference: 100
		"""
		self.encoded_ext_community = bytearray.fromhex(u'0002 D53F 0000 0006 800A 1300 0000 0064')

	def test_l2vpn_decode (self):
		"""
		decode and test against known data

		we do know what routes Juniper sends us and we testing decoded values against it
		"""
		# l2vpn_route1 = VPLS.unpack(str(self.encoded_l2vpn_nlri1))
		# l2vpn_route2 = VPLS.unpack(str(self.encoded_l2vpn_nlri2))
		# self.assertEqual(l2vpn_route1.endpoint,3)
		# self.assertEqual(l2vpn_route1.rd._str(),'172.30.5.4:13')
		# self.assertEqual(l2vpn_route1.offset,1)
		# self.assertEqual(l2vpn_route1.base,262145)
		# self.assertEqual(l2vpn_route1.size,8)
		# self.assertEqual(l2vpn_route2.endpoint,3)
		# self.assertEqual(l2vpn_route2.rd._str(),'172.30.5.3:11')
		# self.assertEqual(l2vpn_route2.offset,1)
		# self.assertEqual(l2vpn_route2.base,262145)
		# self.assertEqual(l2vpn_route2.size,8)

	def test_l2vpn_encode (self):
		"""
		encode and test against known data

		we are encoding routes and testing em against what we have recvd from Juniper
		"""
		# encoded_l2vpn = VPLS(None,None,None,None,None)
		# encoded_l2vpn = self.decoded_l2vpn_nlri1
		# self.assertEqual(
		# 	encoded_l2vpn.pack().encode('hex'),
		# 	str(self.encoded_l2vpn_nlri1).encode('hex')
		# )
		#
		# encoded_l2vpn.nlri = self.decoded_l2vpn_nlri2
		# encoded_l2vpn.rd = self.decoded_l2vpn_nlri2.rd
		# self.assertEqual(
		# 	encoded_l2vpn.pack().encode('hex'),
		# 	str(self.encoded_l2vpn_nlri2).encode('hex')
		# )

	# Disable until we refactor the configuation code
	#
	# def test_l2info_community_decode (self):
	# 	'''
	# 	Juniper sends us both target and l2info; so we test only against
	# 	l2info.
	# 	'''
	# 	l2info_com = ExtendedCommunity.unpack(str(self.encoded_ext_community)[8:16])
	# 	self.assertEqual(l2info_com,to_ExtendedCommunity('l2info:19:0:0:100'))

	# def test_l2info_community_encode (self):
	# 	l2info_com_encoded = to_ExtendedCommunity('l2info:19:0:0:100')
	# 	self.assertEqual(l2info_com_encoded.pack(),str(self.encoded_ext_community)[8:16])

if __name__ == '__main__':
		unittest.main()
