# encoding: utf-8
"""
ip.py

Created by Thomas Mangin on 2010-01-15.
Copyright (c) 2010-2012 Exa Networks. All rights reserved.
"""

import math
import socket

from exabgp.structure.address import AFI,SAFI

mask_to_bytes = {}
for netmask in range(0,129):
	mask_to_bytes[netmask] = int(math.ceil(float(netmask)/8))

def _detect_afi(ip):
	if ip.count(':'):
		return AFI.ipv6
	return AFI.ipv4

def packed_afi (ip):
	afi = _detect_afi(ip)
	return socket.inet_pton(Inet._af[afi],ip),afi

class IPv4 (object):
	def __init__ (self):
		self.packed = '\x00\x00\x00\x00'
		self.ip = '0.0.0.0'

	def ipv4 (self,ipv4):
		self.ip = ipv4
		self.packed = ''.join([chr(int(_)) for _ in ipv4.split('.')])
		return self

	def update (self,packed):
		self.packed = packed
		self.ip = '.'.join([str(ord(_)) for _ in packed])
		return self

	def pack (self):
		return self.packed

	def __len__ (self):
		return 4

	def __str__ (self):
		return self.ip

	def __repr__ (self):
		return self.ip

	def __eq__ (self,other):
		return self.packed == other.packed

class Inet (object):
	_UNICAST = SAFI(SAFI.unicast)
	_MULTICAST = SAFI(SAFI.multicast)
	_MPLS = SAFI(SAFI.nlri_mpls)

	_unicast_range = set(range(224,240)) # 239 is last

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

	def __init__ (self,packed,afi,safi=0):
		self.afi = AFI(afi)
		self.safi = 0 # it get updated with __update
		self.packed = packed
		self.__update()

	def __update (self):
		self.ip = self._ip()

		if not self.safi:
			if self.afi == AFI.ipv4 and int(self.ip.split('.')[0]) in self._unicast_range:
				self.safi = self._MULTICAST
			else:
				self.safi = self._UNICAST
		else:
			self.safi = self._UNICAST

	def update (self,packed):
		self.packed = packed
		self.__update()

	def pack (self):
		return self.packed

	def _ip (self):
		try:
			return socket.inet_ntop(self._af[self.afi],self.packed)
		except socket.error:
			raise ValueError('invalid IP')

	def __len__ (self):
		return len(self.packed)

	def __str__ (self):
		return self.ip

	def __repr__ (self):
		return str(self)

	def __eq__ (self,other):
		return self.packed == other.packed and self.safi == other.safi

def InetIP (ip):
	return Inet(*packed_afi(ip))
