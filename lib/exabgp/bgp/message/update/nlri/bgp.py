# encoding: utf-8
"""
bgp.py

Created by Thomas Mangin on 2012-07-08.
Copyright (c) 2009-2013 Exa Networks. All rights reserved.
"""

from exabgp.protocol.family import AFI,SAFI
from exabgp.bgp.message.update.nlri.prefix import mask_to_bytes,Prefix

from exabgp.bgp.message.update.nlri.qualifier.labels import Labels
from exabgp.bgp.message.update.nlri.qualifier.rd import RouteDistinguisher
from exabgp.bgp.message.update.nlri.qualifier.path import PathInfo

# ====================================================== Both MPLS and Inet NLRI
# RFC ....

class NLRI (Prefix):
	def __init__(self,afi,safi,packed,mask,nexthop,action):
		self.path_info = PathInfo.NOPATH
		self.labels = Labels.NOLABEL
		self.rd = RouteDistinguisher.NORD
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
