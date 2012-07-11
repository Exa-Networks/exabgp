# encoding: utf-8
"""
nlri.py

Created by Thomas Mangin on 2012-07-08.
Copyright (c) 2012 Exa Networks. All rights reserved.
"""

from struct import pack,unpack
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
			self.value = ''
		#sum(int(a)<<offset for (a,offset) in zip(ip.split('.'), range(24, -8, -8)))

	def __len__ (self):
		return len(self.value)

	def __str__ (self):
		if self.value:
			return ' path-information %s' % '.'.join([str(ord(_)) for _ in self.value])
		return ''

	def pack (self):
		if self.value:
			return self.value
		return '\x00\x00\x00\x00'

_NoPathInfo = PathInfo()


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
		if self._len > 1:
			return ' label [ %s ]' % ' '.join([str(_) for _ in self.labels])
		elif self._len == 1:
			return '%s' % self.labels[0]
		else:
			return ''

	def __repr__ (self):
		return str(self)

_NoLabels = Labels([])

class RouteDistinguisher (object):
	def __init__ (self,rd):
		self.rd = rd
		self._len = len(self.rd)

	def pack (self):
		return self.rd

	def __len__ (self):
		return self._len*3 + 1 # length of label

	def __str__ (self):
		if self.rd:
			return ' route-distinguisher %d:%d' % (unpack('!LL',self.rd)[0],unpack('!LL',self.rd)[1])
		return ''
	
	def __repr__ (self):
		return str(self)

_NoRD = RouteDistinguisher('')

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
		self.rd = _NoRD

		BGPPrefix.__init__(self,afi,packed,mask)

	def __len__ (self):
		# 1 is the length of the labels and route
		return len(self.path_info) + 1 + len(self.labels) + len(self.rd) + mask_to_bytes[self.mask]

	def size (self):
		return 

	def __str__ (self):
		return "%s%s%s%s" % (BGPPrefix.__str__(self),str(self.labels),str(self.path_info),str(self.rd))

	def pack (self,with_path_info):
		if with_path_info:
			length = (len(self.path_info) + len(self.labels) + len(self.rd))*8 + self.mask
			payload = chr(length) + self.path_info.pack() + self.labels.pack() + self.rd.pack() + self.packed[:mask_to_bytes[self.mask]]
		else:
			length = (len(self.labels) + len(self.rd))*8 + self.mask
			payload = chr(length) + self.labels.pack() + self.rd.pack() + self.packed[:mask_to_bytes[self.mask]]
		return chr(len(payload)) + payload

# Generate an NLRI suitable for use in Flow Routes
def FlowPrefix (afi,ip,mask):
		packed,afi = packed_afi
		return BGPPrefix(packed,afi,mask)
