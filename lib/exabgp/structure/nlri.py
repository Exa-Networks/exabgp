# encoding: utf-8
"""
nlri.py

Created by Thomas Mangin on 2012-07-08.
Copyright (c) 2012 Exa Networks. All rights reserved.
"""

from exabgp.structure.ip import mask_to_bytes,afi_packed

class PathInfo (object):
	def __init__ (self,integer=None,ip=None,raw=None):
		if raw:
			self.value = raw
		elif ip:
			self.value = ''.join([chr(int(_)) for _ in ip.split('.')])
		elif integer:
			self.value = ''.join([chr((path_info>>offset) & 0xff) for offset in [24,16,8,0]])
		else:
			self.value = ''
		#sum(int(a)<<offset for (a,offset) in zip(ip.split('.'), range(24, -8, -8)))

	def __len__ (self):
		return 4

	def __str__ (self):
		if self.value:
			return " path-information %s" % '.'.join([str(ord(_)) for _ in self.value])
		return ''

	def pack (self):
		return self.value

_NoPathInfo = PathInfo(ip=0)


class BGPPrefix (Inet):
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
		return chr(self.mask) + self.raw[:mask_to_bytes[self.mask]]

	def __len__ (self):
		return mask_to_bytes[self.mask] + 1


class NLRI (BGPPrefix):
	def __init__(self,af,ip,mask):
		self.path_info = _NoPathInfo
		BGPPrefix.__init__(self,af,ip,mask)

	def __len__ (self):
		return len(self.path_info) + BGPPrefix.__len__(self)

	def __str__ (self):
		return "%s%s" % (BGPPrefix.__str__(self),str(self.path_info))

	def pack (self,with_path_info):
		if with_path_info:
			return self.path_info.pack() + BGPPrefix.pack(self)
		return BGPPrefix.pack(self)


# Generate an NLRI from a BGP packet receive
def BGPNLRI (afi,bgp,has_multiple_path):
	if has_multiple_path:
		pi = bgp[:4]
		bgp = bgp[4:]
	else:
		pi = ''
	end = mask_to_bytes[ord(bgp[0])]

	nlri = NLRI(afi,bgp[1:end+1] + '\0'*(NLRI.length[afi]-end),ord(bgp[0]))
	nlri.path_info = PathInfo(raw=pi)

	return nlri


# Generate an NLRI suitable for use in Flow Routes
def FlowNLRI (afi,ip,mask):
		afi,packed = afi_packed
		return BGPPrefix(afi,packed,mask)
