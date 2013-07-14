#!/usr/bin/env python
# encoding: utf-8
"""
protocol.py

Created by Thomas Mangin on 2009-08-27.
Copyright (c) 2009-2013 Exa Networks. All rights reserved.
"""

import unittest

from exabgp.configuration.environment import environment
env = environment.setup('')

from exabgp.bgp.message.open import Open,Capabilities,new_Open
from exabgp.bgp.message.notification import Notification
from exabgp.bgp.message.keepalive import KeepAlive,new_KeepAlive
from exabgp.bgp.message.update import Update,Attributes

from exabgp.rib.table import Table
from exabgp.rib.delta import Delta
from exabgp.reactor.protocol import Protocol
from exabgp.bgp.neighbor import Neighbor

from StringIO import StringIO

class Network (StringIO):
	def pending (self):
		return True

route1 = Update([],[to_NLRI('10.0.0.1','32')],Attributes())
route1.next_hop = '10.0.0.254'

route2 = Update([],[to_NLRI('10.0.1.1','32')],Attributes())
route2.next_hop = '10.0.0.254'

route3 = Update([],[to_NLRI('10.0.2.1','32')],Attributes())
route3.next_hop = '10.0.0.254'

routes = [route1,route2,route3]
routes.sort()

class TestProtocol (unittest.TestCase):

	def setUp(self):
		self.table = Table()
		self.table.update(routes)
		self.neighbor = Neighbor()
		self.neighbor.local_as = ASN(65000)
		self.neighbor.peer_as = ASN(65000)
		self.neighbor.peer_address = InetIP('1.2.3.4')
		self.neighbor.local_address = InetIP('5.6.7.8')

	def test_4_selfparse_update_announce (self):
		o = Open(4,65000,'1.2.3.4',Capabilities().default(),30).message()
		k = KeepAlive().message()
		u = Delta(self.table).announce(65000,65000)
		network = Network(o+k+ ''.join(u))
		bgp = Protocol(self.neighbor,network)
		bgp.follow = False

		self.assertEqual(bgp.read_message().TYPE,Open.TYPE)
		self.assertEqual(bgp.read_message().TYPE,KeepAlive.TYPE)
		updates = bgp.read_message()
		self.assertEqual(updates.TYPE,Update.TYPE)
		self.assertEqual(str(updates.added()[0]),'10.0.0.1/32 next-hop 10.0.0.254')
		updates = bgp.read_message()
		self.assertEqual(updates.TYPE,Update.TYPE)
		self.assertEqual(str(updates.added()[0]),'10.0.2.1/32 next-hop 10.0.0.254')
		updates = bgp.read_message()
		self.assertEqual(updates.TYPE,Update.TYPE)
		self.assertEqual(str(updates.added()[0]),'10.0.1.1/32 next-hop 10.0.0.254')

	def test_5_selfparse_update_announce_multi (self):
		o = Open(4,65000,'1.2.3.4',Capabilities().default(),30).message()
		k = KeepAlive().message()
		d = Delta(self.table)
		a = d.announce(65000,65000)
		self.table.update(routes[:-1])
		u = d.update(65000,65000)

		network = Network(o+k+''.join(u))
		bgp = Protocol(self.neighbor,network)
		bgp.follow = False

		self.assertEqual(bgp.read_message().TYPE,Open.TYPE)
		self.assertEqual(bgp.read_message().TYPE,KeepAlive.TYPE)
		updates = bgp.read_message()
		self.assertEqual(updates.TYPE,Update.TYPE)
		self.assertEqual(str(updates.added()[0]),'10.0.2.1/32')

if __name__ == '__main__':
	unittest.main()
