# encoding: utf-8
"""
nlri.py

Created by Thomas Mangin on 2012-07-08.
Copyright (c) 2009-2013 Exa Networks. All rights reserved.
"""

import math

from struct import pack,unpack
from exabgp.protocol.family import AFI,SAFI
from exabgp.protocol.ip.inet import Inet

from exabgp.protocol.ip.address import Address
from exabgp.bgp.message.update.attribute.attributes import Attributes

from exabgp.bgp.message.notification import Notify

mask_to_bytes = {}
for netmask in range(0,129):
	mask_to_bytes[netmask] = int(math.ceil(float(netmask)/8))

# Take an integer an created it networked packed representation for the right family (ipv4/ipv6)
def pack_int (afi,integer,mask):
	return ''.join([chr((integer>>(offset*8)) & 0xff) for offset in range(NLRI.length[afi]-1,-1,-1)])


class PathInfo (object):
	def __init__ (self,integer=None,ip=None,packed=None):
		if packed:
			self.value = packed
		elif ip:
			self.value = ''.join([chr(int(_)) for _ in ip.split('.')])
		elif integer:
			self.value = ''.join([chr((integer>>offset) & 0xff) for offset in [24,16,8,0]])
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

	def __str__ (self):
		if not self.rd:
			return ''

		t,c1,c2,c3 = unpack('!HHHH',self.rd)
		if t == 0:
			rd = '%d:%d' % (c1,(c2<<16)+c3)
		elif t == 1:
			rd = '%d.%d.%d.%d:%d' % (c1>>8,c1&0xFF,c2>>8,c2&0xFF,c3)
		elif t == 2:
			rd = '%d:%d' % ((c1<<16)+c2,c3)
		else:
			rd = str(self.rd)

		if self.rd:
			return ' route-distinguisher %s' % rd
		return ''

_NoRD = RouteDistinguisher('')

class BGPPrefix (Inet):
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


class NLRI (BGPPrefix):
	def __init__(self,afi,safi,packed,mask):
		self.path_info = _NoPathInfo
		self.labels = _NoLabels
		self.rd = _NoRD

		BGPPrefix.__init__(self,afi,safi,packed,mask)

	def has_label (self):
		if self.afi == AFI.ipv4 and self.safi in (SAFI.nlri_mpls,SAFI.mpls_vpn):
			return True
		if self.afi == AFI.ipv6 and self.safi == SAFI.mpls_vpn:
			return True
		return False

	def __len__ (self):
		prefix_len = len(self.path_info) + len(self.labels) + len(self.rd)
		return 1 + prefix_len + mask_to_bytes[self.mask]

	def __str__ (self):
		return "%s%s%s%s" % (BGPPrefix.__str__(self),str(self.labels),str(self.path_info),str(self.rd))

	def __eq__ (self,other):
		return str(self) == str(other)

	def __ne__ (self,other):
		return not self.__eq__(other)

	def json (self):
		label = str(self.labels)
		pinfo = str(self.path_info)
		rdist = str(self.rd)

		r = []
		if label: r.append('"label": "%s"' % label)
		if pinfo: r.append('"path-information": "%s"' % pinfo)
		if rdist: r.append('"route-distinguisher": "%s"' % rdist)
		return '"%s": { %s }' % (BGPPrefix.__str__(self),", ".join(r))

	def pack (self,addpath):
		if addpath:
			path_info = self.path_info.pack()
		else:
			path_info = ''

		if self.has_label():
			length = len(self.labels)*8 + len(self.rd)*8 + self.mask
			return path_info + chr(length) + self.labels.pack() + self.rd.pack() + self.packed[:mask_to_bytes[self.mask]]
		else:
			return path_info + BGPPrefix.pack(self)

# Generate an NLRI from a BGP packet receive
def BGPNLRI (afi,safi,bgp,has_multiple_path):
	labels = []
	rd = ''

	if has_multiple_path:
		path_identifier = bgp[:4]
		bgp = bgp[4:]
	else:
		path_identifier = ''

	mask = ord(bgp[0])
	bgp = bgp[1:]

	if SAFI(safi).has_label():
		while bgp and mask >= 8:
			label = int(unpack('!L',chr(0) + bgp[:3])[0])
			bgp = bgp[3:]
			labels.append(label>>4)
			mask -= 24  # 3 bytes
			if label & 1:
				break
			# This is a route withdrawal, or next-hop
			if label == 0x000000 or label == 0x80000:
				break

	if SAFI(safi).has_rd():
		mask -= 8*8  # the 8 bytes of the route distinguisher
		rd = bgp[:8]
		bgp = bgp[8:]

	if mask < 0:
		raise Notify(3,10,'invalid length in NLRI prefix')

	if not bgp and mask:
		raise Notify(3,10,'not enough data for the mask provided to decode the NLRI')

	size = mask_to_bytes[mask]

	if len(bgp) < size:
		raise Notify(3,10,'could not decode route with AFI %d sand SAFI %d' % (afi,safi))

	network = bgp[:size]
	# XXX: The padding calculation should really go into the NLRI class
	padding = '\0'*(NLRI.length[afi]-size)
	prefix = network + padding
	nlri = NLRI(afi,safi,prefix,mask)

	# XXX: Not the best interface but will do for now
	if safi:
		nlri.safi = SAFI(safi)

	if path_identifier:
		nlri.path_info = PathInfo(packed=path_identifier)
	if labels:
		nlri.labels = Labels(labels)
	if rd:
		nlri.rd = RouteDistinguisher(rd)
	return nlri


class Route (object):
	def __init__ (self,nlri):
		self.nlri = nlri
		self.attributes = Attributes()

	def __str__ (self):
		return "route %s%s" % (str(self.nlri),str(self.attributes))

	def __hash__(self):
		return hash(str(self))

	def __eq__(self, other):
		return str(self) == str(other)

	def __ne__ (self,other):
		return not self.__eq__(other)

	def extensive (self):
		return "%s %s%s" % (str(Address(self.nlri.afi,self.nlri.safi)),str(self.nlri),str(self.attributes))

	def index (self):
		return self.nlri.pack(True)+self.nlri.rd.rd


class RouteBGP (Route):
	def __init__ (self,nlri,action):
		self.action = action  # announce, announced, withdraw or withdrawn
		Route.__init__(self,nlri)

	def __str__ (self):
		return "%s %s" % (self.action,Route.__str__(self))

def routeFactory(afi,safi,data,path_info,state):
	return RouteBGP(BGPNLRI(afi,safi,data,path_info),state)
