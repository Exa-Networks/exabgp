# encoding: utf-8
"""
bgp.py

Created by Thomas Mangin on 2012-07-08.
Copyright (c) 2009-2013 Exa Networks. All rights reserved.
"""

from struct import pack,unpack
from exabgp.protocol.family import AFI,SAFI

from exabgp.bgp.message.update.nlri.prefix import mask_to_bytes,Prefix

class PathInfo (object):
	def __init__ (self,integer=None,ip=None,packed=None):
		if packed:
			self.path_info = packed
		elif ip:
			self.path_info = ''.join([chr(int(_)) for _ in ip.split('.')])
		elif integer:
			self.path_info = ''.join([chr((integer>>offset) & 0xff) for offset in [24,16,8,0]])
		else:
			self.path_info = ''
		#sum(int(a)<<offset for (a,offset) in zip(ip.split('.'), range(24, -8, -8)))

	def __len__ (self):
		return len(self.path_info)

	def json (self):
		return '"path-information": "%s"' % '.'.join([str(ord(_)) for _ in self.path_info])

	def __str__ (self):
		if self.path_info:
			return ' path-information %s' % '.'.join([str(ord(_)) for _ in self.path_info])
		return ''

	def pack (self):
		if self.path_info:
			return self.path_info
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

	def json (self):
		if self._len > 1:
			return '"label": [ %s ]' % ', '.join([str(_) for _ in self.labels])
		else:
			return ''

	def __str__ (self):
		if self._len > 1:
			return ' label [ %s ]' % ' '.join([str(_) for _ in self.labels])
		elif self._len == 1:
			return ' label %s' % self.labels[0]
		else:
			return ''

_NoLabels = Labels([])

class RouteDistinguisher (object):
	def __init__ (self,rd):
		self.rd = rd
		self._len = len(self.rd)

	def pack (self):
		return self.rd

	def __len__ (self):
		return self._len

	def _str (self):
		t,c1,c2,c3 = unpack('!HHHH',self.rd)
		if t == 0:
			rd = '%d:%d' % (c1,(c2<<16)+c3)
		elif t == 1:
			rd = '%d.%d.%d.%d:%d' % (c1>>8,c1&0xFF,c2>>8,c2&0xFF,c3)
		elif t == 2:
			rd = '%d:%d' % ((c1<<16)+c2,c3)
		else:
			rd = str(self.rd)
		return rd

	def json (self):
		if not self.rd:
			return ''
		return '"route-distinguisher": "%s"' % self._str()

	def __str__ (self):
		if not self.rd:
			return ''
		return ' route-distinguisher %s' % self._str()

_NoRD = RouteDistinguisher('')


class NLRI (Prefix):
	def __init__(self,afi,safi,packed,mask,nexthop,action):
		self.path_info = _NoPathInfo
		self.labels = _NoLabels
		self.rd = _NoRD
		self.nexthop = nexthop
		self.action = action

		Prefix.__init__(self,afi,safi,packed,mask)

	def has_label (self):
		if self.afi == AFI.ipv4 and self.safi in (SAFI.nlri_mpls,SAFI.mpls_vpn):
			return True
		if self.afi == AFI.ipv6 and self.safi == SAFI.mpls_vpn:
			return True
		return False

	def nlri (self):
		return "%s%s%s%s" % (self.prefix(),str(self.labels),str(self.path_info),str(self.rd))

	def __len__ (self):
		prefix_len = len(self.path_info) + len(self.labels) + len(self.rd)
		return 1 + prefix_len + mask_to_bytes[self.mask]

	def __str__ (self):
		nexthop = ' next-hop %s' % self.nexthop.inet() if self.nexthop else ''
		return "%s%s" % (self.nlri(),nexthop)

	def __eq__ (self,other):
		return str(self) == str(other)

	def __ne__ (self,other):
		return not self.__eq__(other)

	def json (self,announced=True):
		label = self.labels.json()
		pinfo = self.path_info.json()
		rdist = self.rd.json()

		r = []
		if announced:
			if self.labels: r.append(label)
			if self.rd: r.append(rdist)
			if self.nexthop: r.append('"next-hop": "%s"' % self.nexthop.inet())
		if self.path_info: r.append(pinfo)
		return '"%s": { %s }' % (self.prefix(),", ".join(r))

	def pack (self,addpath):
		if addpath:
			path_info = self.path_info.pack()
		else:
			path_info = ''

		if self.has_label():
			length = len(self.labels)*8 + len(self.rd)*8 + self.mask
			return path_info + chr(length) + self.labels.pack() + self.rd.pack() + self.packed[:mask_to_bytes[self.mask]]
		else:
			return path_info + Prefix.pack(self)

	def index (self):
		return self.pack(True)+self.rd.rd+self.path_info.path_info
