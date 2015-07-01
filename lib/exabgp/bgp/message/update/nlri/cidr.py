# encoding: utf-8
"""
prefix.py

Created by Thomas Mangin on 2013-08-07.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

import math
from exabgp.protocol.ip import IP


class CIDR (object):
	EOR = False
	# we can not define slots here as otherwise it conflict in Prefix
	# __slots__ = ['packed','mask','_ip']

	_mask_to_bytes = {}

	@classmethod
	def size (cls, mask):
		return cls._mask_to_bytes.get(mask,0)

	# have a .raw for the ip
	# have a .mask for the mask
	# have a .bgp with the bgp wire format of the prefix

	def __init__ (self, packed, mask):
		self._packed = packed
		self.mask = mask
		self._ip = None

	def __eq__ (self, other):
		return \
			self.mask == other.mask and \
			self._packed == other.packed

	def __ne__ (self, other):
		return \
			self.mask != other.mask or \
			self._packed != other.packed

	def __lt__ (self, other):
		raise RuntimeError('comparing CIDR for ordering does not make sense')

	def __le__ (self, other):
		raise RuntimeError('comparing CIDR for ordering does not make sense')

	def __gt__ (self, other):
		raise RuntimeError('comparing CIDR for ordering does not make sense')

	def __ge__ (self, other):
		raise RuntimeError('comparing CIDR for ordering does not make sense')

	def top (self):
		if not self._ip:
			self._ip = IP.ntop(self._packed)
		return self._ip

	def ton (self):
		return self._packed

	def __repr__ (self):
		return self.prefix()

	def prefix (self):
		return "%s/%s" % (self.top(),self.mask)

	def cidr (self):
		return chr(self.mask) + self._packed[:CIDR.size(self.mask)]

	def classless (self):
		return self._packed[:CIDR.size(self.mask)]

	# July 2014: should never be called as it is for the RIB code only
	# def index (self):
	# 	return self.pack()

	def __len__ (self):
		return CIDR.size(self.mask) + 1

	def __hash__ (self):
		return hash(chr(self.mask)+self._packed)


for netmask in range(0,129):
	CIDR._mask_to_bytes[netmask] = int(math.ceil(float(netmask)/8))
