# encoding: utf-8
"""
ip.py

Created by Thomas Mangin on 2010-01-15.
Copyright (c) 2009-2013  Exa Networks. All rights reserved.
"""

import socket

from exabgp.protocol.family import AFI,SAFI
from exabgp.protocol.ip.address import Address

def _detect_afi(ip):
	if ip.count(':'):
		return AFI.ipv6
	return AFI.ipv4

def _detect_safi (ip):
	if '.' in ip and int(ip.split('.')[0]) in Inet._multicast_range:
		return SAFI.multicast
	else:
		return SAFI.unicast

def inet (ip):
	afi = _detect_afi(ip)
	safi = _detect_safi(ip)
	return afi,safi,socket.inet_pton(Inet._af[afi],ip)

def pton (ip):
	afi = _detect_afi(ip)
	return socket.inet_pton(Inet._af[afi],ip)

def rawinet (packed):
	afi = AFI.ipv4 if len(packed) == 4 else AFI.ipv6
	safi = SAFI.multicast if ord(packed[0]) in Inet._multicast_range else SAFI.unicast
	return afi,safi,packed

class Inet (Address):
	_UNICAST = SAFI(SAFI.unicast)
	_MULTICAST = SAFI(SAFI.multicast)

	_multicast_range = set(range(224,240))  # 239 is last

	"""An IP in the 4 bytes format"""
	# README: yep, we should surely change this _ name here
	_af = {
		AFI.ipv4: socket.AF_INET,
		AFI.ipv6: socket.AF_INET6,
	}

	_afi = {
		socket.AF_INET : AFI.ipv4,
		socket.AF_INET6: AFI.ipv6,
	}

	length = {
		AFI.ipv4:  4,
		AFI.ipv6: 16,
	}

	def __init__ (self,afi,safi,packed):
		if safi:  # XXX: FIXME: we use a constant which is zero - reference it explicitly
			Address.__init__(self,afi,safi)
		elif ord(packed[0]) in self._multicast_range:
			Address.__init__(self,afi,self._MULTICAST)
		else:
			Address.__init__(self,afi,self._UNICAST)

		self.packed = packed
		self.ip = socket.inet_ntop(self._af[self.afi],self.packed)

	def pack (self):
		return self.packed

	def __len__ (self):
		return len(self.packed)

	def inet (self):
		return self.ip

	def __str__ (self):
		return self.inet()

	def __cmp__ (self,other):
		if self.packed == other.packed:
			return 0
		if self.packed < other.packed:
			return -1
		return 1

	def __repr__ (self):
		return "<%s value %s>" % (str(self.__class__).split("'")[1].split('.')[-1],str(self))
