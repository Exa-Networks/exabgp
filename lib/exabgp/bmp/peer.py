# encoding: utf-8
"""
peer.py

Created by Thomas Mangin on 2013-02-26.
Copyright (c) 2009-2012 Exa Networks. All rights reserved.
"""

from struct import unpack
from socket import inet_ntop, AF_INET, AF_INET6

class PeerType (int):
	_str = {
		0 : 'global',
		1 : 'L3 VPN',
	}

	def __str__ (self):
		return self._str.get(self,'unknow %d' % self)

class PeerFlag (int):
	_v4v6 = 0b10000000

	def ipv4 (self):
		return not self & self._v4v6

	def ipv6 (self):
		return bool(self & self._v4v6)

class Peer (object):
	def __init__ (self,data):
		self.type = PeerType(ord(data[2]))
		self.flag = PeerFlag(ord(data[3]))
		self.distinguisher = unpack('!L',data[4:8])[0]
		self.asn = unpack('!L',data[28:32])[0]
		self.id = inet_ntop(AF_INET, data[32:36])

		if self.flag.ipv4(): self.peer_address = inet_ntop(AF_INET, data[24:28])
		if self.flag.ipv6(): self.peer_address = inet_ntop(AF_INET6, data[12:28])

	def validate (self):
		return self.type in (0,1)
