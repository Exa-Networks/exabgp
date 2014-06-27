# encoding: utf-8
"""
prefix.py

Created by Thomas Mangin on 2013-08-07.
Copyright (c) 2009-2013 Exa Networks. All rights reserved.
"""

import math
import socket

mask_to_bytes = {}
for netmask in range(0,129):
	mask_to_bytes[netmask] = int(math.ceil(float(netmask)/8))


class Prefix (object):
	# have a .raw for the ip
	# have a .mask for the mask
	# have a .bgp with the bgp wire format of the prefix

	def __init__(self,packed,mask):
		self.packed = packed
		self.mask = mask
		self._ip = None

	@property
	def ip (self):
		if not self._ip:
			self._ip = socket.inet_ntop(socket.AF_INET if len(self.packed) == 4 else socket.AF_INET6,self.packed)
		return self._ip

	def __str__ (self):
		return self.prefix()

	def prefix (self):
		return "%s/%s" % (self.ip,self.mask)

	def pack (self):
		return chr(self.mask) + self.packed[:mask_to_bytes[self.mask]]

	def packed_ip(self):
		return self.packed[:mask_to_bytes[self.mask]]

	def index (self):
		return self.pack()

	def __len__ (self):
		return mask_to_bytes[self.mask] + 1

	def __eq__(self,other):
		if not isinstance(other,Prefix):
			return False
		return self.pack() == other.pack()

	def __hash__(self):
		return hash(self.pack())
