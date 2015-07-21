# encoding: utf-8
"""
bgp.py

Created by Thomas Mangin on 2012-07-08.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

# from exabgp.protocol.family import AFI
# from exabgp.protocol.family import SAFI

from exabgp.bgp.message import OUT

# from exabgp.bgp.message.update.nlri.nlri import NLRI
from exabgp.bgp.message.update.nlri.cidr import CIDR
from exabgp.bgp.message.update.nlri.mpls import MPLS
# from exabgp.bgp.message.update.nlri.qualifier import RouteDistinguisher


# ====================================================== Both MPLS and Inet NLRI
# RFC 3107 / RFC 4364

# @NLRI.register(AFI.ipv4,SAFI.mpls_vpn)
# @NLRI.register(AFI.ipv6,SAFI.mpls_vpn)
class MPLSVPN (MPLS):
	def __init__ (self, afi, safi, action=OUT.UNSET):
		MPLS.__init__(self, afi, safi, action)

	@classmethod
	def new (cls, afi, safi, packed, mask, nexthop):
		instance = cls(afi,safi,OUT.ANNOUNCE)
		instance.cidr = CIDR(packed, mask)
		instance.nexthop = nexthop
		return instance

	def __eq__(self, other):
		# Note: BaGPipe needs an advertise and a withdraw for the same
		# RD:prefix to result in objects that are equal for Python,
		# this is why the test below does not look at self.labels nor
		# self.nexthop or self.action

		# Note to Note: This breaks all ExaBGP API consistency
		# Are we not better having a new comparator function, or have bagpipe-bgp
		# Inherit and replace the __eq__ function with its own version
		# using @NLRI.register(AFI.ipv4,SAFI.mpls_vpn,force=True)
		return \
			isinstance(other, MPLSVPN) and \
			self.path_info == other.path_info and \
			self.rd == other.rd and \
			self.cidr == other.cidr

	def __hash__(self):
		# Like for the comparaison, two NLRI with same RD and prefix, but
		# different labels need to hash equal
		# XXX: Don't we need to have the label here ?
		return hash((self.rd, self.cidr.top(), self.cidr.mask))
