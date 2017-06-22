# encoding: utf-8
"""
bgp.py

Created by Thomas Mangin on 2012-07-08.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

from exabgp.protocol.family import AFI
from exabgp.protocol.family import SAFI

from exabgp.protocol.ip import IP
from exabgp.protocol.ip import NoIP
from exabgp.bgp.message.update.nlri.nlri import NLRI
from exabgp.bgp.message.update.nlri.cidr import CIDR
from exabgp.bgp.message.update.nlri.qualifier.labels import Labels
from exabgp.bgp.message.update.nlri.qualifier.rd import RouteDistinguisher
from exabgp.bgp.message.update.nlri.qualifier.path import PathInfo


# ====================================================== Both MPLS and Inet NLRI
# RFC ....

class MPLS (NLRI,CIDR):
	__slots__ = ['labels','rd','nexthop','action']

	def __init__ (self, afi, safi, packed, mask, nexthop, action):
		self.path_info = PathInfo.NOPATH
		self.labels = Labels.NOLABEL
		self.rd = RouteDistinguisher.NORD
		self.nexthop = IP.unpack(nexthop) if nexthop else NoIP
		self.action = action
		NLRI.__init__(self,afi,safi)
		CIDR.__init__(self,packed,mask)

	def index (self):
		return self.pack() + self.nexthop.pack()

	def has_label (self):
		if self.afi == AFI.ipv4 and self.safi in (SAFI.nlri_mpls,SAFI.mpls_vpn):
			return True
		if self.afi == AFI.ipv6 and self.safi == SAFI.mpls_vpn:
			return True
		return False

	def extensive (self):
		nexthop = ' next-hop %s' % self.nexthop if self.nexthop else ''
		return "%s%s%s%s%s" % (self.prefix(),nexthop,str(self.labels),str(self.path_info),str(self.rd))

	def __len__ (self):
		return CIDR.__len__(self) + len(self.labels) + len(self.rd)

	def __str__ (self):
		return self.extensive()

	def __eq__ (self,other):
		return self.index() == other.index()

	def __ne__ (self, other):
		return not self.__eq__(other)

	def __hash__ (self):
		return hash(self.pack())

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
			if addpath:
				return self.path_info.pack() + CIDR.pack(self)
			return CIDR.pack(self)

		length = len(self.labels)*8 + len(self.rd)*8 + self.mask
		if addpath:
			return self.path_info.pack() + chr(length) + self.labels.pack() + self.rd.pack() + CIDR.packed_ip(self)
		return chr(length) + self.labels.pack() + self.rd.pack() + CIDR.packed_ip(self)

	def index (self):
		return self.pack(self.path_info != PathInfo.NOPATH)

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
