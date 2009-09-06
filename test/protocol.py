#!/usr/bin/env python
# encoding: utf-8
"""
protocol.py

Created by Thomas Mangin on 2009-08-27.
Copyright (c) 2009 Exa Networks. All rights reserved.
"""

import unittest
from StringIO import StringIO

from bgp.table import Table
from bgp.data import IP,ASN,Route,Neighbor
from bgp.message import Message, Open, Update, Notification, KeepAlive
from bgp.protocol import Protocol

class Network (StringIO):
	def pending (self):
		return True


class TestProtocol (unittest.TestCase):
	routes = [Route('10.0.0.1','32','10.0.0.254'),Route('10.0.1.1','32','10.0.0.254'),Route('10.0.2.1','32','10.0.0.254')]

	def setUp(self):
		self.table = Table()
		self.table.update(self.routes)
		self.neighbor = Neighbor()
		self.neighbor.local_as = ASN(65000)
		self.neighbor.peer_as = ASN(65000)
		self.neighbor.peer_address = IP('1.2.3.4')
	
	def test_selfparse_open (self):
		ds = Open(65000,'1.2.3.4',30,4)
		
		txt = ds.message()
		network = Network(txt)
		#print [hex(ord(c)) for c in txt]
		bgp = Protocol(self.neighbor,network)
		bgp.follow = False

		o = bgp.read_open()
		self.assertEqual(o.version,4)
		self.assertEqual(o.asn,65000)
		self.assertEqual(o.hold_time,30)
		self.assertEqual(str(o.router_id),'1.2.3.4')
	
	def test_selfparse_update_announce (self):
		ds = Update(self.table)

		txt = ds.announce(65000,65000)
		network = Network(txt)
		bgp = Protocol(self.neighbor,network)
		bgp.follow = False

		m,_ = bgp.read_message()
		self.assertEqual(m,chr(2))

	def test_selfparse_update_announce_multi (self):
		ds = Update(self.table)
		
		txt  = ds.announce(65000,65000)
		txt += ds.update(65000,65000)
		network = Network(txt)

		bgp = Protocol(self.neighbor,network)
		bgp.follow = False

		m,_ = bgp.read_message()
		self.assertEqual(m,chr(2))
		m,_ = bgp.read_message()
		self.assertEqual(m,chr(2))
		m,_ = bgp.read_message()
		self.assertEqual(m,chr(2))
		m,d = bgp.read_message()
		self.assertEqual(m,chr(2))
		self.assertEqual(d,chr(0)*4) 

		self.assertEqual(network.read(1),'')
		#print [hex(ord(c)) for c in msg.read(1024)]

	def test_selfparse_KeepAlive (self):
		ds = KeepAlive()

		txt = ds.message()
		network = Network(txt)
		bgp = Protocol(self.neighbor,network)

		m,d = bgp.read_message()
		self.assertEqual(m,chr(4))
	
if __name__ == '__main__':
	unittest.main()