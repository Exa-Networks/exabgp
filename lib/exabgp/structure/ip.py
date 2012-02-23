#!/usr/bin/env python
# encoding: utf-8
"""
ip.py

Created by Thomas Mangin on 2010-01-15.
Copyright (c) 2010-2012 Exa Networks. All rights reserved.
"""

import math
import socket

from exabgp.structure.address import AFI,SAFI #,Address
from exabgp.message.update.route import Route

_bgp = {}
for netmask in range(0,129):
	_bgp[netmask] = int(math.ceil(float(netmask)/8))

def _detect_afi(ip):
	if ip.count(':'):
		return AFI.ipv6
	return AFI.ipv4

def to_IP (ip):
	afi = _detect_afi(ip)
	af = Inet._af[afi]
	network = socket.inet_pton(af,ip)
	return Inet(afi,network)

def to_Route (ip,mask):
	afi = _detect_afi(ip)
	return Route(Prefix(afi,ip,mask))

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

	_length = {
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

class _Prefix (Inet):
	# have a .raw for the ip
	# have a .mask for the mask
	# have a .bgp with the bgp wire format of the prefix

	def __init__(self,af,ip,mask):
		self.mask = int(mask)
		Inet.__init__(self,af,ip)

	def __str__ (self):
		return "%s/%s" % (self.ip,self.mask)

	def __repr__ (self):
		return str(self)

	def pack (self):
		return chr(self.mask) + self.raw[:_bgp[self.mask]]

	def __len__ (self):
		return _bgp[self.mask] + 1


class BGPPrefix (_Prefix):
	"""From the BGP prefix wire format, Store an IP (in the network format), its netmask and the bgp format"""
	def __init__ (self,afi,bgp):
		end = _bgp[ord(bgp[0])]
		_Prefix.__init__(self,afi,bgp[1:end+1] + '\0'*(self._length[afi]-end),ord(bgp[0]))

class AFIPrefix (_Prefix):
	"""Store an IP (in the network format), its netmask and the bgp format of the IP"""
	def __init__ (self,afi,network,mask):
		_Prefix.__init__(self,afi,network,mask)

class Prefix (_Prefix):
	"""Store an IP (in the network format), its netmask and the bgp format of the IP"""
	def __init__ (self,afi,ip,mask):
		af = self._af[afi]
		network = socket.inet_pton(af,ip)
		_Prefix.__init__(self,afi,network,mask)
