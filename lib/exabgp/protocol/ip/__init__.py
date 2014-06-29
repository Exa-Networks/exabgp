# encoding: utf-8
"""
ip/__init__.py

Created by Thomas Mangin on 2010-01-15.
Copyright (c) 2009-2013  Exa Networks. All rights reserved.
"""

import socket

from exabgp.protocol.family import AFI,SAFI

def _detect_afi(ip):
	if ':' in ip:
		return AFI.ipv6
	return AFI.ipv4

def _detect_safi (ip):
	if '.' in ip and int(ip.split('.')[0]) in IP._multicast_range:
		return SAFI.multicast
	else:
		return SAFI.unicast

def inet (ip):
	afi = _detect_afi(ip)
	safi = _detect_safi(ip)
	return afi,safi,socket.inet_pton(IP._af[afi],ip)

def pton (ip):
	afi = _detect_afi(ip)
	return socket.inet_pton(IP._af[afi],ip)

class IP (object):
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

	def __init__ (self,ip,packed=None):
		self.ip = ip
		self.packed = packed if packed else socket.inet_pton(IP._af[_detect_afi(ip)],ip)

	def unicast (self):
		return not self.multicast()

	def multicast (self):
		return ord(self.packed[0]) in set(range(224,240))

	def ipv4 (self):
		return len(self) == 4

	def ipv6 (self):
		return len(self) > 4

	def pack (self):
		return self.packed

	def __len__ (self):
		return len(self.packed)

	# XXX: FIXME: This API should be able to go away
	def inet (self):
		return self.ip

	def __str__ (self):
		return self.ip

	def __repr__ (self):
		return str(self)

	def __cmp__ (self,other):
		if self.packed == other.packed:
			return 0
		if self.packed < other.packed:
			return -1
		return 1

	@classmethod
	def unpack (cls,data,klass=None):
		afi = AFI.ipv4 if len(data) == 4 else AFI.ipv6

		if klass:
			return klass(socket.inet_ntop(IP._af[afi],data))
		return cls(socket.inet_pton(IP._af[afi],data))
