# encoding: utf-8
"""
bgp.py

Created by Thomas Mangin on 2012-07-08.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

from exabgp.protocol.family import AFI
from exabgp.protocol.family import SAFI

from exabgp.protocol.ip import IP
from exabgp.protocol.ip import NoNextHop
from exabgp.bgp.message.update.nlri.nlri import NLRI
from exabgp.bgp.message.update.nlri.cidr import CIDR
from exabgp.bgp.message.update.nlri.qualifier import Labels
from exabgp.bgp.message.update.nlri.qualifier import RouteDistinguisher
from exabgp.bgp.message.update.nlri.qualifier import PathInfo


# ====================================================== Both MPLS and Inet NLRI
# RFC 3107 / RFC 4364

@NLRI.register(AFI.ipv4,SAFI.nlri_mpls)
@NLRI.register(AFI.ipv6,SAFI.nlri_mpls)
class MPLS (NLRI,CIDR):
	__slots__ = ['labels','rd','nexthop','action']

	def __init__ (self, afi, safi, packed, mask, nexthop, action,path=None):
		self.path_info = PathInfo.NOPATH if path is None else path
		self.labels = Labels.NOLABEL
		self.rd = RouteDistinguisher.NORD
		self.nexthop = IP.unpack(nexthop) if nexthop else NoNextHop
		self.action = action
		NLRI.__init__(self,afi,safi)
		CIDR.__init__(self,packed,mask)

	def has_label (self):
		if self.afi == AFI.ipv4 and self.safi in (SAFI.nlri_mpls,SAFI.mpls_vpn):
			return True
		if self.afi == AFI.ipv6 and self.safi == SAFI.mpls_vpn:
			return True
		return False

	def extensive (self):
		return "%s%s%s%s" % (self.prefix(),str(self.labels),str(self.path_info),str(self.rd))

	def __len__ (self):
		return CIDR.__len__(self) + len(self.labels) + len(self.rd)

	def __repr__ (self):
		nexthop = ' next-hop %s' % self.nexthop if self.nexthop else ''
		return "%s%s" % (self.extensive(),nexthop)

	def __eq__ (self, other):
		return \
			NLRI.__eq__(self, other) and \
			CIDR.__eq__(self, other) and \
			self.path_info == other.path_info and \
			self.labels == other.labels and \
			self.rd == other.rd and \
			self.nexthop == other.nexthop and \
			self.action == other.action

	def __ne__ (self, other):
		return not self.__eq__(other)

	def json (self, announced=True):
		label = self.labels.json()
		rdist = self.rd.json()
		pinfo = self.path_info.json()

		r = []
		if announced:
			if label:
				r.append(label)
			if rdist:
				r.append(rdist)
			if pinfo:
				r.append(pinfo)
		return '"%s": { %s }' % (self.prefix(),", ".join(r))

	def pack (self, addpath=None):
		if not self.has_label():
			return CIDR.pack(self)

		length = len(self.labels)*8 + len(self.rd)*8 + self.mask
		return chr(length) + self.labels.pack() + self.rd.pack() + CIDR.packed_ip(self)

	def index (self):
		return self.pack()

	@classmethod
	def unpack (cls, afi, safi, bgp, addpath, nexthop, action):
		labels,rd,path_identifier,mask,size,prefix,left = NLRI._nlri(afi,safi,bgp,action,addpath)

		nlri = cls(afi,safi,prefix,mask,nexthop,action)
		if labels:
			nlri.labels = Labels(labels)
		if rd:
			nlri.rd = RouteDistinguisher(rd)
		if path_identifier:
			nlri.path_info = PathInfo(None,None,path_identifier)

		return len(bgp) - len(left),nlri


# ====================================================== Both MPLS and Inet NLRI
# RFC 3107 / RFC 4364

@NLRI.register(AFI.ipv4,SAFI.mpls_vpn)
@NLRI.register(AFI.ipv6,SAFI.mpls_vpn)
class MPLSVPN (MPLS):

	def __init__(self, afi, safi, packedPrefix, mask, labels, rd, nexthop, action=None, path=None):
		MPLS.__init__(self, afi, safi, packedPrefix, mask, nexthop, action,path)
		# assert(isinstance(rd,RouteDistinguisher))
		self.rd = rd
		if labels is None:
			labels = Labels.NOLABEL
		# assert(isinstance(labels,Labels))
		self.labels = labels

	def __eq__(self, other):
		# Note: BaGPipe needs an advertise and a withdraw for the same
		# RD:prefix to result in objects that are equal for Python,
		# this is why the test below does not look at self.labels
		return \
			MPLS.__eq__(self,other) and \
			self.rd == other.rd and \
			self.prefix == other.prefix

	def __ne__ (self, other):
		return not self.__eq__(other)

	def __hash__(self):
		# Like for the comparaison, two NLRI with same RD and prefix, but
		# different labels need to hash equal
		return hash((self.rd, self.ip, self.mask))

	def __str__(self):
		return "%s,%s/%d:%s" % (self.rd._str(), self.ip, self.mask, repr(self.labels))

	@classmethod
	def unpack (cls, afi, safi, bgp, addpath, nexthop, action):
		labels,rd,path_identifier,mask,size,prefix,left = NLRI._nlri(afi,safi,bgp,action,addpath)
		nlri = cls(afi, safi, prefix, mask, Labels(labels), RouteDistinguisher(rd), nexthop, action, path=None)
		if path_identifier:
			nlri.path_info = PathInfo(None,None,path_identifier)
		return len(bgp) - len(left),nlri
