#!/usr/bin/env python
# encoding: utf-8
"""
family.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009 Exa Networks. All rights reserved.
"""

# =================================================================== AFI

# http://www.iana.org/assignments/address-family-numbers/
class AFI (int):
	ipv4 = 0x01
	ipv6 = 0x02

	def __str__ (self):
		if self == 0x01: return "IPv4"
		if self == 0x02: return "IPv6"
		return "unknown afi"

	def pack (self):
		return pack('!H',self)

# =================================================================== SAFI

# http://www.iana.org/assignments/safi-namespace
class SAFI (int):
	unicast = 1					# [RFC4760]
	multicast = 2				# [RFC4760]
#	deprecated = 3				# [RFC4760]
#	nlri_mpls = 4				# [RFC3107]
#	mcast_vpn = 5				# [draft-ietf-l3vpn-2547bis-mcast-bgp] (TEMPORARY - Expires 2008-06-19)
#	pseudowire = 6				# [draft-ietf-pwe3-dynamic-ms-pw] (TEMPORARY - Expires 2008-08-23) Dynamic Placement of Multi-Segment Pseudowires
#	encapsulation = 7			# [RFC5512]
#
#	tunel = 64					# [Nalawade]
#	vpls = 65					# [RFC4761]
#	bgp_mdt = 66				# [Nalawade]
#	bgp_4over6 = 67				# [Cui]
#	bgp_6over4 = 67				# [Cui]
#	vpn_adi = 69				# [RFC-ietf-l1vpn-bgp-auto-discovery-05.txt]
#
#	mpls_vpn = 128				# [RFC4364]
#	mcast_bgp_mpls_vpn = 129	# [RFC2547]
#	rt = 132					# [RFC4684]
#	flow_ipv4 = 133				# [RFC5575]
#	flow_vpnv4 = 134			# [RFC5575]
#
#	vpn_ad = 140				# [draft-ietf-l3vpn-bgpvpn-auto]
#
#	private = [_ for _ in range(241,254)]	# [RFC4760]
#	unassigned = [_ for _ in range(8,64)] + [_ for _ in range(70,128)]
#	reverved = [0,3] + [130,131] + [_ for _ in range(135,140)] + [_ for _ in range(141,241)] + [255,]	# [RFC4760]

	def __str__ (self):
		if self == 0x01: return "unicast"
		if self == 0x02: return "multicast"
		return "unknown safi"

	def pack (self):
		return chr(self)
