#!/usr/bin/env python
# encoding: utf-8
"""
ip.py

Created by Thomas Mangin on 2010-01-15.
Copyright (c) 2010 Exa Networks. All rights reserved.
"""

from struct import pack
import math
import socket

from bgp.interface import IByteStream
from bgp.structure.afi import AFI
from bgp.structure.safi import SAFI
from bgp.structure.nlri import NLRI

_bgp = {}
for mask in range(0,129):
	_bgp[mask] = int(math.ceil(float(mask)/8))


def to_Prefix (value):
	if value.count(':'):
		raw = socket.inet_pton(socket.AF_INET6,value)
		return to_Prefix(AFI.ipv6,value)
	raw = socket.inet_pton(socket.AF_INET,value)
	return to_Prefix4(AFI.ipv4,value)


class Inet (IByteStream):
	"""An IP in the 4 bytes format"""
	_af = {
		AFI.ipv4: socket.AF_INET,
		AFI.ipv6: socket.AF_INET6,
	}

	_length = {
		socket.AF_INET  :  4,
		socket.AF_INET6 : 16,
	}

	def __init__ (self,af,ip):
		self.af = af
		self.ip = ip

	def pack (self):
		return self.network

	def __str__ (self):
		return socket.inet_ntop(self.af,self.ip)

class IPrefix (Inet):
	# have a .ip for the ip
	# have a .mask for the mask
	# have a .bgp with the bgp wire format of the prefix

	def __init__(self,af,ip,mask):
		self.mask = mask
		Inet.__init__(self,af,ip)

	def __str__ (self):
		return "%s/%s" % (socket.inet_ntop(self.af,self.ip),self.mask)

	def pack (self):
		return chr(self.mask) + self.ip[:_bgp[self.mask]]


class BGPPrefix (IPrefix):
	"""From the BGP prefix wire format, Store an IP (in the network format), its netmask and the bgp format"""
	def __init__ (self,afi,bgp):
		af = self._af[afi]
		IPrefix.__init__(self,af,bgp[1:] + '\0'*(self._length[af]+1-len(bgp)),ord(bgp[0]))

class AFIPrefix (IPrefix):
	"""Store an IP (in the network format), its netmask and the bgp format of the IP"""
	def __init__ (self,afi,network,mask):
		af = self._af[afi]
		IPrefix.__init__(self,af,network,mask)

class Prefix (IPrefix):
	"""Store an IP (in the network format), its netmask and the bgp format of the IP"""
	def __init__ (self,afi,ip,mask):
		af = self._af[afi]
		network = socket.inet_pton(af,ip)
		IPrefix.__init__(self,af,network,mask)
