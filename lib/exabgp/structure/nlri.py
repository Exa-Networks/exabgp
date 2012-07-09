# encoding: utf-8
"""
nlri.py

Created by Thomas Mangin on 2012-07-08.
Copyright (c) 2012 Exa Networks. All rights reserved.
"""

from struct import pack
from exabgp.structure.ip import mask_to_bytes,packed_afi,Inet

class PathInfo (object):
	def __init__ (self,integer=None,ip=None,packed=None):
		if packed:
			self.value = packed
		elif ip:
			self.value = ''.join([chr(int(_)) for _ in ip.split('.')])
		elif integer:
			self.value = ''.join([chr((path_info>>offset) & 0xff) for offset in [24,16,8,0]])
		else:
			self.value = None
		#sum(int(a)<<offset for (a,offset) in zip(ip.split('.'), range(24, -8, -8)))

	def __len__ (self):
		return 4

	def __str__ (self):
		if self.value:
			return ' path-information %s' % '.'.join([str(ord(_)) for _ in self.value])
		return ''

	def pack (self):
		if self.value:
			return self.value
		return '\x00\x00\x00\x00'

_NoPathInfo = PathInfo(ip=0)


class Labels (object):
	biggest = pow(2,20)

	def __init__ (self,labels):
		self.labels = labels
		packed = []
		for label in labels:
			# shift to 20 bits of the label to be at the top of three bytes and then truncate.
			packed.append(pack('!L',label << 4)[1:])
		# Mark the bottom of stack with the bit
		if packed:
			packed.pop()
			packed.append(pack('!L',(label << 4)|1)[1:])
		self.packed = ''.join(packed)
		self._len = len(self.packed)

	def pack (self):
		return self.packed

	def __len__ (self):
		return self._len

	def __str__ (self):
		if self._len != 1:
			return ' label [ %s ]' % ' '.join([str(_) for _ in self.labels])
		return '%s' % self.labels[0]

	def __repr__ (self):
		return str(self)

_NoLabels = Labels([])

class BGPPrefix (Inet):
	# have a .raw for the ip
	# have a .mask for the mask
	# have a .bgp with the bgp wire format of the prefix

	def __init__(self,packed,afi,mask):
		self.mask = int(mask)
		Inet.__init__(self,packed,afi)

	def __str__ (self):
		return "%s/%s" % (self.ip,self.mask)

	def __repr__ (self):
		return str(self)

	def pack (self):
		return chr(self.mask) + self.packed[:mask_to_bytes[self.mask]]

	def __len__ (self):
		return mask_to_bytes[self.mask] + 1


class NLRI (BGPPrefix):
	def __init__(self,afi,packed,mask):
		self.path_info = _NoPathInfo
		self.labels = _NoLabels

		BGPPrefix.__init__(self,afi,packed,mask)

	def __len__ (self):
		return len(self.path_info) + len(self.labels) + BGPPrefix.__len__(self)

	def __str__ (self):
		return "%s%s%s" % (BGPPrefix.__str__(self),str(self.labels),str(self.path_info))

	def pack (self,with_path_info):
		if with_path_info:
			return self.path_info.pack() + self.labels.pack() + BGPPrefix.pack(self)
		return self.labels.pack() + BGPPrefix.pack(self)

# Generate an NLRI suitable for use in Flow Routes
def FlowPrefix (afi,ip,mask):
		packed,afi = packed_afi
		return BGPPrefix(packed,afi,mask)
