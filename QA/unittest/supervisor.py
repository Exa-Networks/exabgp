#!/usr/bin/env python
# encoding: utf-8
"""
peer.py

Created by Thomas Mangin on 2009-08-30.
Copyright (c) 2009-2013 Exa Networks. All rights reserved.
"""

import unittest

from exabgp.configuration.environment import environment
env = environment.setup('')

from exabgp.configuration.file import Configuration
from exabgp.reactor import Reactor

class TestPeer (unittest.TestCase):
	text_configuration = """\
neighbor 192.0.2.181 {
	description "a quagga test peer";
	router-id 192.0.2.92;
	local-address 192.0.2.92;
	local-as 65000;
	peer-as 65000;

	static {
		route 10.0.5.0/24 next-hop 192.0.2.92 local-preference 10 community [ 0x87654321 ];
	}
}
"""

	def setUp(self):
		self.configuration = Configuration(self.text_configuration,True)
		self.assertEqual(self.configuration.reload(),True,"could not read the configuration, run the configuration unittest")

	def test_connection (self):
		reactor = Reactor(self.configuration)
		reactor.run()
		#self.failIf()

if __name__ == '__main__':
	unittest.main()
