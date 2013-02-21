# encoding: utf-8
"""
ip.py

Created by Thomas Mangin on 2010-01-15.
Copyright (c) 2009-2013  Exa Networks. All rights reserved.
"""

import socket

from exabgp.protocol.family import AFI,SAFI

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


class Inet (object):
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
		self.afi = AFI(afi)
		if safi:
			self.safi = SAFI(safi)
		elif ord(packed[0]) in self._multicast_range:
			self.safi = self._MULTICAST
		else:
			self.safi = self._UNICAST
		self.packed = packed
		self.ip = socket.inet_ntop(self._af[self.afi],self.packed)

	def pack (self):
		return self.packed

	def __len__ (self):
		return len(self.packed)

	def __str__ (self):
		return self.ip

	def __eq__ (self,other):
		return self.packed == other.packed and self.safi == other.safi

	def __ne__ (self,other):
		return not self.__eq__(other)

	def __repr__ (self):
		return "<%s value %s>" % (str(self.__class__).split("'")[1].split('.')[-1],str(self))
