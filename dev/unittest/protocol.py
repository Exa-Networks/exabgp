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
from exabgp.bgp.message.update import Update,Attributes,new_Update

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
		self.neighbor = Neighbor()
		self.neighbor.local_as = ASN(65000)
		self.neighbor.peer_as = ASN(65000)
		self.neighbor.peer_address = InetIP('1.2.3.4')
		self.neighbor.local_address = InetIP('5.6.7.8')

	def test_1_selfparse_open (self):
		ds = Open(4,65000,'1.2.3.4',Capabilities().default(),30)

		txt = ds.message()
		network = Network(txt)
		#print [hex(ord(c)) for c in txt]
		bgp = Protocol(self.neighbor,network)
		bgp.follow = False

		o = bgp.read_open('127.0.0.1')
		self.assertEqual(o.version,4)
		self.assertEqual(o.asn,65000)
		self.assertEqual(o.hold_time,30)
		self.assertEqual(str(o.router_id),'1.2.3.4')

	def test_2_selfparse_KeepAlive (self):
		ds = KeepAlive()

		txt = ds.message()
		network = Network(txt)
		bgp = Protocol(self.neighbor,network)

		message = bgp.read_message()
		self.assertEqual(message.TYPE,KeepAlive.TYPE)

	def test_3_parse_update (self):
		txt = ''.join([chr(c) for c in [0x0, 0x0, 0x0, 0x1c, 0x40, 0x1, 0x1, 0x2, 0x40, 0x2, 0x0, 0x40, 0x3, 0x4, 0xc0, 0x0, 0x2, 0xfe, 0x80, 0x4, 0x4, 0x0, 0x0, 0x0, 0x0, 0x40, 0x5, 0x4, 0x0, 0x0, 0x1, 0x23, 0x20, 0x52, 0xdb, 0x0, 0x7, 0x20, 0x52, 0xdb, 0x0, 0x45, 0x20, 0x52, 0xdb, 0x0, 0x47]])
		updates = new_Update(txt)

		routes = [str(route) for route in updates.added()]
		routes.sort()
		self.assertEqual(routes[0],'82.219.0.69/32 next-hop 192.0.2.254')
		self.assertEqual(routes[1],'82.219.0.7/32 next-hop 192.0.2.254')
		self.assertEqual(routes[2],'82.219.0.71/32 next-hop 192.0.2.254')

	def test_4_parse_update (self):
		txt = ''.join([chr(c) for c in [0x0, 0x0, 0x0, 0x12, 0x40, 0x1, 0x1, 0x0, 0x40, 0x2, 0x4, 0x2, 0x1, 0x78, 0x14, 0x40, 0x3, 0x4, 0x52, 0xdb, 0x2, 0xb5, 0x0]])
		updates = new_Update(txt)
		self.assertEqual(str(updates.added()[0]),'0.0.0.0/0 next-hop 82.219.2.181')

	def test_6_holdtime (self):
		class MyPeer(Network):
			_data = StringIO(Open(4,65000,'1.2.3.4',Capabilities().default(),90).message())
			def read (self,l):
				return self._data.read(l)

		network = MyPeer('')

		bgp = Protocol(self.neighbor,network)
		bgp.follow = False

		before = bgp.neighbor.hold_time
		bgp.new_open()
		bgp.read_open('127.0.0.1')
		after = bgp.neighbor.hold_time

		self.assertEqual(after,min(before,90))

#	def test_7_message (self):
#		txt = ''.join([chr(_) for _ in [0x0, 0x0, 0x0, 0x30, 0x40, 0x1, 0x1, 0x0, 0x50, 0x2, 0x0, 0x4, 0x2, 0x1, 0xff, 0xfe, 0x80, 0x4, 0x4, 0x0, 0x0, 0x0, 0x0, 0x80, 0xe, 0x1a, 0x0, 0x2, 0x1, 0x10, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x20, 0x12, 0x34, 0x56, 0x78]])
#		updates = new_Update(txt)
#		print updates
#		self.assertEqual(str(updates.added()[0]),'1234:5678::/32 next-hop ::')

#	def test_7_ipv6 (self):
#		txt = ''.join([chr(_) for _ in [0x0, 0x0, 0x0, 0x25, 0x40, 0x1, 0x1, 0x0, 0x40, 0x2, 0x4, 0x2, 0x1, 0xfd, 0xe8, 0xc0, 0x8, 0x8, 0x78, 0x14, 0x0, 0x0, 0x78, 0x14, 0x78, 0x14, 0x40, 0xf, 0xc, 0x0, 0x2, 0x1, 0x40, 0x2a, 0x2, 0xb, 0x80, 0x0, 0x0, 0x0, 0x1]])
#		updates = new_Update(txt)

if __name__ == '__main__':
	unittest.main()
