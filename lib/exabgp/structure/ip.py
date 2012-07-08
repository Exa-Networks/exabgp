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

def afi_packed (ip):
	afi = _detect_afi(ip)
	return afi,socket.inet_pton(Inet._af[afi],ip)

class IPv4 (object):
	def __init__ (self):
		self.raw = '\x00\x00\x00\x00'
		self.ip = '0.0.0.0'

	def ipv4 (self,ipv4):
		self.ip = ipv4
		self.raw = ''.join([chr(int(_)) for _ in ipv4.split('.')])
		return self

	def raw (self,raw):
		self.raw = raw
		self.ip = '.'.join([str(ord(_)) for _ in raw])
		return self

	def pack (self):
		return self.raw

	def __len__ (self):
		return 4

	def __str__ (self):
		return self.ip

	def __repr__ (self):
		return self.ip

	def __eq__ (self,other):
		return self.raw == other.raw

class Inet (object):
	_UNICAST = SAFI(SAFI.unicast)
	_MULTICAST = SAFI(SAFI.multicast)
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

	def __init__ (self,afi,raw):
		self.afi = AFI(afi)
		self.raw = raw
		self.__update()

	def __update (self):
		self.ip = self._ip()

		if self.afi == AFI.ipv4 and int(self.ip.split('.')[0]) in self._unicast_range:
			self.safi = self._MULTICAST
		else:
			self.safi = self._UNICAST

	def update_raw (self,raw):
		self.raw = raw
		self.__update()

	def pack (self):
		return self.raw

	def _ip (self):
		try:
			return socket.inet_ntop(self._af[self.afi],self.raw)
		except socket.error:
			raise ValueError('invalid IP')

	def __len__ (self):
		return len(self.raw)

	def __str__ (self):
		return self.ip

	def __repr__ (self):
		return str(self)

	def __eq__ (self,other):
		return self.raw == other.raw and self.safi == other.safi

def InetIP (ip):
	return Inet(*afi_packed(ip))
