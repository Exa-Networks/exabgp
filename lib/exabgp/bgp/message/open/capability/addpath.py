#!/usr/bin/env python
# encoding: utf-8
"""
addpath.py

Created by Thomas Mangin on 2012-07-17.
Copyright (c) 2012 Exa Networks. All rights reserved.
"""

from struct import pack

from exabgp.bgp.message.open.capability.id import CapabilityID

# =================================================================== AddPath

class AddPath (dict):
	string = {
		0 : 'disabled',
		1 : 'receive',
		2 : 'send',
		3 : 'send/receive',
	}

	def __init__ (self,families=[],send_receive=0):
		for afi,safi in families:
			self.add_path(afi,safi,send_receive)

	def add_path (self,afi,safi,send_receive):
		self[(afi,safi)] = send_receive

	def __str__ (self):
		return 'AddPath(' + ','.join(["%s %s %s" % (self.string[self[aafi]],xafi,xsafi) for (aafi,xafi,xsafi) in [((afi,safi),str(afi),str(safi)) for (afi,safi) in self]]) + ')'

	def extract (self):
		rs = []
		for v in self:
			if self[v]:
				rs.append(v[0].pack() +v[1].pack() + pack('!B',self[v]))
		return rs

# =================================================================== AddPath

class UsePath (object):
	REFUSE = 0
	ACCEPT = 1
	ANNOUNCE = 2

	def __init__(self,received_open,sent_open):
		# A Dict always returning False
		class FalseDict (dict):
			def __getitem__(self,key):
				return False

		receive = received_open.capabilities.get(CapabilityID.ADD_PATH,FalseDict())
		send = sent_open.capabilities.get(CapabilityID.ADD_PATH,FalseDict())

		self._send = {}
		self._receive = {}

		# python 2.4 compatibility mean no simple union but using sets.Set
		union = []
		union.extend(send.keys())
		union.extend([k for k in receive.keys() if k not in send.keys()])

		for k in union:
			self._send[k] = bool(receive.get(k,self.REFUSE) & self.ANNOUNCE and send.get(k,self.REFUSE) & self.ACCEPT)
			self._receive[k] = bool(receive.get(k,self.REFUSE) & self.ACCEPT and send.get(k,self.REFUSE) & self.ANNOUNCE)

	def send (self,afi,safi):
		return self._send.get((afi,safi),False)

	def receive (self,afi,safi):
		return self._receive.get((afi,safi),False)

