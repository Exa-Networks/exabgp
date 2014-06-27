# encoding: utf-8
"""
routerid.py

Created by Thomas Mangin on 2012-07-17.
Copyright (c) 2009-2013 Exa Networks. All rights reserved.
"""

import socket
from exabgp.protocol.family import AFI,SAFI
from exabgp.protocol.ip.address import Address

# ===================================================================== RouterID

class RouterID (Address):
	def __init__ (self,ip,packed=None):
		Address.__init__(self,AFI.ipv4,SAFI.unicast)
		self.ip = ip
		self.packed = packed if packed else socket.inet_pton(socket.AF_INET,ip)

	def pack (self):
		return self.packed

	def __len__ (self):
		return 4

	def inet (self):
		return self.ip

	def __str__ (self):
		return self.ip

	def __repr__ (self):
		return str(self)

	def __cmp__ (self,other):
		if not isinstance(other, self.__class__):
			return -1
		if self.packed == other.packed:
			return 0
		if self.packed < other.packed:
			return -1
		return 1

	@classmethod
	def unpack (cls,data):
		return cls('.'.join(str(ord(_)) for _ in data),data)
