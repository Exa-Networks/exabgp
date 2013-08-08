# encoding: utf-8
"""
nlri/__init__.py

Created by Thomas Mangin on 2013-08-07.
Copyright (c) 2009-2013 Exa Networks. All rights reserved.
"""

import math
from exabgp.protocol.ip.inet import Inet

mask_to_bytes = {}
for netmask in range(0,129):
	mask_to_bytes[netmask] = int(math.ceil(float(netmask)/8))

# Take an integer an created it networked packed representation for the right family (ipv4/ipv6)
def pack_int (afi,integer,mask):
	return ''.join([chr((integer>>(offset*8)) & 0xff) for offset in range(Inet.length[afi]-1,-1,-1)])

class GenericNLRI (Inet):
	# have a .raw for the ip
	# have a .mask for the mask
	# have a .bgp with the bgp wire format of the prefix

	def __init__(self,afi,safi,packed,mask):
		self.mask = int(mask)
		Inet.__init__(self,afi,safi,packed)

	def __str__ (self):
		return "%s/%s" % (self.ip,self.mask)

	# The API requires addpath, but it is irrelevant here.
	def pack (self,addpath=None):
		return chr(self.mask) + self.prefix()

	def prefix (self):
		return self.packed[:mask_to_bytes[self.mask]]

	def __len__ (self):
		return mask_to_bytes[self.mask] + 1
