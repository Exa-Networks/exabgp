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

def to_Prefix (value):
	if value.count(':'):
		return to_Prefix6(value)
	return to_Prefix4(value)

class IPrefix (IByteStream):
	_af = {
		AFI.ipv4: {
			SAFI.unicast :  socket.AF_INET,
		},
		AFI.ipv6: {
			SAFI.unicast : socket.AF_INET6,
		},
	}

	_length = {
		AFI.ipv4: {
			SAFI.unicast :  4,
		},
		AFI.ipv6: {
			SAFI.unicast : 16
		},
	}

	# have a .ip for the ip
	# have a .mask for the mask
	# have a .bgp with the bgp wire format of the prefix

	def __str__ (self):
		return "%s/%s" % (self.str,ord(self.mask))

	def pack (self):
		return self.bgp


class Prefix (IPrefix):
	"""Store an IP (in the network format), its netmask and the bgp format of the IP"""
	def __init__ (self,afi,safi,ip,mask):
		inet = self._af.setdefault(afi,{}).get(safi,None)
		if inet is None:
			raise NotImplemented('This AFI/SAFI pair is not implemented as Prefix (%s/%s)' % (AFI(afi),SAFI(safi)))

		network = socket.inet_pton(inet,ip)
		size = int(math.ceil(float(mask)/8))

		self.ip = network
		self.mask = chr(mask)
		self.bgp = self.mask + network[:size]
		self.str = socket.inet_ntop(inet,network)

class AFIPrefix (IPrefix):
	"""Store an IP (in the network format), its netmask and the bgp format of the IP"""
	def __init__ (self,afi,safi,ip,mask):
		inet = self._af.setdefault(afi,{}).get(safi,None)
		if inet is None:
			raise NotImplemented('This AFI/SAFI pair is not implemented as Prefix (%s/%s)' % (AFI(afi),SAFI(safi)))

		size = int(math.ceil(float(mask)/8))

		self.ip = ip
		self.mask = chr(mask)
		self.bgp = self.mask + ip[:size]
		self.str = socket.inet_ntop(inet,ip)

class BGPPrefix (IPrefix):
	"""From the BGP prefix wire format, Store an IP (in the network format), its netmask and the bgp format"""
	def __init__ (self,afi,safi,bgp):
		inet = self._af.setdefault(afi,{}).get(safi,None)
		if inet is None:
			raise NotImplemented('This AFI/SAFI pair is not implemented as Prefix (%s/%s)' % (AFI(afi),SAFI(safi)))

		length = self._length.setdefault(afi,{}).get(safi,None)
		network = bgp[1:] + '\0'*(length+1-len(bgp))

		self.ip = network
		self.mask = bgp[0]
		self.bgp = bgp
		self.str = socket.inet_ntop(inet,network)
