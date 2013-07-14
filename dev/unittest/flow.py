#!/usr/bin/env python
# encoding: utf-8
"""
flow.py

Created by Thomas Mangin on 2010-01-14.
Copyright (c) 2009-2013  Exa Networks. All rights reserved.
"""

import unittest

from exabgp.configuration.environment import environment
env = environment.setup('')

from exabgp.bgp.message.update.nlri.flow import *
from exabgp.protocol.ip.inet import *
from exabgp.bgp.message.update.attribute.communities import *


class TestFlow (unittest.TestCase):

	def setUp(self):
		pass

	def test_rule (self):
		components = {
			'destination': Destination("192.0.2.0",24),
			'source'     : Source("10.1.2.0",24),
			'anyport_1'  : AnyPort(NumericOperator.EQ,25),
		}
		messages = {
			'destination': [0x01, 0x18, 0xc0, 0x00, 0x02],
			'source'     : [0x02, 0x18, 0x0a, 0x01, 0x02],
			'anyport_1'  : [0x04, 0x01, 0x19],
		}

		for key in components.keys():
			component = components[key].pack()
			message   = ''.join((chr(_) for _ in messages[key]))
			if component != message:
				self.fail('failed test %s\n%s\n%s\n' % (key, [hex(ord(_)) for _ in component], [hex(ord(_)) for _ in message]))

	def test_rule_and (self):
		components = {
			'destination': Destination("192.0.2.0",24),
			'source'     : Source("10.1.2.0",24),
			'anyport_1'  : AnyPort(NumericOperator.EQ|NumericOperator.GT,25),
			'anyport_2'  : AnyPort(NumericOperator.EQ|NumericOperator.LT,80),
		}
		messages = {
			'destination': [0x01, 0x18, 0xc0, 0x00, 0x02],
			'source'     : [0x02, 0x18, 0x0a, 0x01, 0x02],
			'anyport_1'  : [0x04, 0x43, 0x19],
			'anyport_2'  : [0x04, 0x85, 0x50],
		}

		policy = Policy()
		message = ""
		for key in ['destination','source','anyport_1','anyport_2']:
			policy.add_and(components[key])
			message += ''.join([chr(_) for _ in messages[key]])
		message = chr(len(message)) + message
		policy.add(to_FlowAction(65000,False,False))
		flow = policy.flow().pack()
		#print [hex(ord(_)) for _ in flow]

	def test_nlri (self):
		components = {
			'destination': Destination("192.0.2.0",24),
			'source'     : Source("10.1.2.0",24),
			'anyport_1'  : AnyPort(NumericOperator.EQ|NumericOperator.GT,25),
			'anyport_2'  : AnyPort(NumericOperator.EQ|NumericOperator.LT,80),
		}
		messages = {
			'destination': [0x01, 0x18, 0xc0, 0x00, 0x02],
			'source'     : [0x02, 0x18, 0x0a, 0x01, 0x02],
			'anyport_1'  : [0x04, 0x43, 0x19],
			'anyport_2'  : [0x85, 0x50],
		}

		policy = Policy()
		message = ""
		for key in ['destination','source','anyport_1','anyport_2']:
			policy.add_and(components[key])
			message += ''.join([chr(_) for _ in messages[key]])
		message = chr(len(message)) + message
		policy.add(to_FlowAction(65000,False,False))
		flow = policy.flow().pack()
		if message[0] != flow[0]:
			self.fail('size mismatch %s %s\n' % (ord(flow[0]),ord(message[0])))
		if len(flow) != ord(flow[0]) + 1:
			self.fail('invalid size for message')
		if message[1:] != flow[1:]:
			self.fail('content mismatch\n%s\n%s' % ( [hex(ord(_)) for _ in flow]  , [hex(ord(_)) for _ in message] ))

#	def test_update (self):
#		components = {
#			'source_dest_port' : [Destination("192.0.2.0",24), Source("10.1.2.0",24), AnyPort(NumericOperator.EQ,25)],
#		}
#
#		messages = {
#			'source_dest_port' : [0x0f, 0x01, 0x04, 0x18, 0xc0, 0x00, 0x02, 0x02, 0x04, 0x18, 0x0a, 0x01, 0x02, 0x04, 0x81, 0x19],
#		}
#
#		for key in components.keys():
#			policy = Policy()
#			for component in components[key]:
#				policy.add_and(component)
#			policy.add(to_FlowAction(65000,False,False))
#			update = policy.flow().update().announce(0,0)
#			message   = ''.join((chr(_) for _ in messages[key]))
#			if update != message:
#				self.fail('failed test %s\n%s\n%s\n' % (key, [hex(ord(_)) for _ in update], [hex(ord(_)) for _ in message]))

if __name__ == '__main__':
	unittest.main()
