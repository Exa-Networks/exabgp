#!/usr/bin/env python
# encoding: utf-8
"""
update.py

Created by Thomas Mangin on 2009-09-06.
Copyright (c) 2009-2013 Exa Networks. All rights reserved.
"""

import unittest

from exabgp.configuration.environment import environment
env = environment.setup('')

from exabgp.bgp.message.open import *

class TestData (unittest.TestCase):

	def test_1_open (self):
		header = ''.join([chr(c) for c in [0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0x0, 0x3d, 0x1]])
		message = ''.join([chr(c) for c in [0x4, 0xff, 0xfe, 0x0, 0xb4, 0x0, 0x0, 0x0, 0x0, 0x20, 0x2, 0x6, 0x1, 0x4, 0x0, 0x1, 0x0, 0x1, 0x2, 0x6, 0x1, 0x4, 0x0, 0x2, 0x0, 0x1, 0x2, 0x2, 0x80, 0x0, 0x2, 0x2, 0x2, 0x0, 0x2, 0x6, 0x41, 0x4, 0x0, 0x0, 0xff, 0xfe]])
		o  = new_Open(message)
		self.assertEqual(o.version,4)
		self.assertEqual(o.asn,65534)
		self.assertEqual(o.router_id,'0.0.0.0')
		self.assertEqual(o.hold_time,180)
		self.assertEqual(o.capabilities, {128: [], 1: [(1, 1), (2, 1)], 2: [], 65: 65534})

	def test_2_open (self):
		o = Open(4,65500,'127.0.0.1',Capabilities().default(False),180)
		self.assertEqual(o.version,4)
		self.assertEqual(o.asn,65500)
		self.assertEqual(o.router_id,'127.0.0.1')
		self.assertEqual(o.hold_time,180)
		self.assertEqual(o.capabilities, {64: {(1, 1): 128, (2, 1): 128}, 1: [(1, 1), (2, 1)]})

if __name__ == '__main__':
	unittest.main()
