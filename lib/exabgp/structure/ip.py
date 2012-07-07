# encoding: utf-8
"""
ip.py

Created by Thomas Mangin on 2010-01-15.
Copyright (c) 2010-2012 Exa Networks. All rights reserved.
"""

import math
import socket

from exabgp.structure.address import AFI,SAFI
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
	network = socket.inet_pton(AFI.Family[afi],ip)
	return Route(NLRI(afi,network,mask))

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

class Prefix (_Prefix):
	"""Store an IP (in the network format), its netmask and the bgp format of the IP"""
	def __init__ (self,afi,ip,mask):
		af = self._af[afi]
		network = socket.inet_pton(af,ip)
		Prefix.__init__(self,afi,network,mask,path_info)

class NLRI (_Prefix):
	def __init__(self,af,ip,mask,path_info=None):
		if path_info is not None:
			self.path_info = ''.join([chr((path_info>>offset) & 0xff) for offset in [24,16,8,0]])
		else:
			self.path_info = ''

		_Prefix.__init__(self,af,ip,mask)

	def __len__ (self):
		return _Prefix.__len__(self) + len(self.path_info)

	def __str__ (self):
		if self.path_info:
			return "%s path-information %s" % (_Prefix.__str__(self),socket.inet_ntoa(self.path_info))
		return _Prefix.__str__(self)

	def pack (self):
		return self.path_info + _Prefix.pack(self)

	def add_path (self,value):
		self.path_info = ''.join([chr((value>>offset) & 0xff) for offset in [24,16,8,0]])

class BGPPrefix (NLRI):
	"""From the BGP prefix wire format, Store an IP (in the network format), its netmask and the bgp format"""
	def __init__ (self,afi,bgp,has_multiple_path):
		if has_multiple_path:
			pi = bgp[:4]
			bgp = bgp[4:]
		else:
			pi = ''
		end = _bgp[ord(bgp[0])]
		NLRI.__init__(self,afi,bgp[1:end+1] + '\0'*(self._length[afi]-end),ord(bgp[0]))
		self.path_info = pi
