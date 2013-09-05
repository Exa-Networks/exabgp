# encoding: utf-8
"""
prefix.py

Created by Thomas Mangin on 2013-08-07.
Copyright (c) 2009-2013 Exa Networks. All rights reserved.
"""

import math
from exabgp.protocol.ip.inet import Inet

mask_to_bytes = {}
for netmask in range(0,129):
	mask_to_bytes[netmask] = int(math.ceil(float(netmask)/8))


class Prefix (Inet):
	# have a .raw for the ip
	# have a .mask for the mask
	# have a .bgp with the bgp wire format of the prefix

	def __init__(self,afi,safi,packed,mask):
		self.mask = mask
		Inet.__init__(self,afi,safi,packed)

	def __str__ (self):
		return self.prefix()

	def prefix (self):
		return "%s/%s" % (self.ip,self.mask)

	def pack (self):
		return chr(self.mask) + self.packed[:mask_to_bytes[self.mask]]

	def packed_ip(self):
		return self.packed[:mask_to_bytes[self.mask]]

	def __len__ (self):
		return mask_to_bytes[self.mask] + 1
