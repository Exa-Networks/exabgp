# encoding: utf-8
"""
bgp.py

Created by Thomas Mangin on 2012-07-08.
Copyright (c) 2009-2013 Exa Networks. All rights reserved.
"""

from exabgp.protocol.ip import IP
from exabgp.protocol.family import AFI,SAFI

from exabgp.bgp.message.update.nlri.nlri import NLRI
from exabgp.bgp.message.update.nlri.cidr import CIDR
from exabgp.bgp.message.update.nlri.qualifier.labels import Labels
from exabgp.bgp.message.update.nlri.qualifier.rd import RouteDistinguisher


# ====================================================== Both MPLS and Inet NLRI
# RFC ....

class MPLS (NLRI,CIDR):
	def __init__(self,afi,safi,packed,mask,nexthop,action):
		self.labels = Labels.NOLABEL
		self.rd = RouteDistinguisher.NORD
		self.nexthop = nexthop
		self.action = action
		NLRI.__init__(self,afi,safi)
		CIDR.__init__(self,packed,mask)

	def has_label (self):
		if self.afi == AFI.ipv4 and self.safi in (SAFI.nlri_mpls,SAFI.mpls_vpn):
			return True
		if self.afi == AFI.ipv6 and self.safi == SAFI.mpls_vpn:
			return True
		return False

	def nlri (self):
		return "%s%s%s" % (self.prefix(),str(self.labels),str(self.rd))

	def __len__ (self):
		return CIDR.__len__(self) + len(self.labels) + len(self.rd)

	def __str__ (self):
		nexthop = ' next-hop %s' % self.nexthop if self.nexthop else ''
		return "%s%s" % (self.nlri(),nexthop)

	def __eq__ (self,other):
		return str(self) == str(other)

	def __ne__ (self,other):
		return not self.__eq__(other)

	def json (self,announced=True):
		label = self.labels.json()
		rdist = self.rd.json()

		r = []
		if announced:
			if self.labels: r.append(label)
			if self.rd: r.append(rdist)
		return '"%s": { %s }' % (self.prefix(),", ".join(r))

	def pack (self,addpath=None):
		if not self.has_label():
			return CIDR.pack(self)

		length = len(self.labels)*8 + len(self.rd)*8 + self.mask
		return chr(length) + self.labels.pack() + self.rd.pack() + CIDR.packed_ip(self)

	def index (self):
		return self.pack()

	@classmethod
	def unpack (cls,afi,safi,bgp,addpath,nexthop,action):
		labels,rd,mask,size,prefix,left = NLRI._nlri(afi,safi,bgp,action)

		nlri = cls(afi,safi,prefix,mask,IP.unpack(nexthop),action)
		if labels: nlri.labels = Labels(labels)
		if rd: nlri.rd = RouteDistinguisher(rd)

		return len(bgp) - len(left),nlri

for safi in (SAFI.nlri_mpls, SAFI.mpls_vpn):
	for afi in (AFI.ipv4, AFI.ipv6):
		MPLS.register(afi,safi)
