# encoding: utf-8
"""
address.py

Created by Thomas Mangin on 2010-01-19.
Copyright (c) 2009-2013  Exa Networks. All rights reserved.
"""

from struct import pack

# =================================================================== AFI

# http://www.iana.org/assignments/address-family-numbers/
class AFI (int):
	ipv4 = 0x01
	ipv6 = 0x02

	Family = {
		ipv4 : 0x02,  # socket.AF_INET,
		ipv6 : 0x30,  # socket.AF_INET6,
	}

	def __str__ (self):
		if self == 0x01: return "ipv4"
		if self == 0x02: return "ipv6"
		return "unknown afi"

	def name (self):
		if self == 0x01: return "inet4"
		if self == 0x02: return "inet6"
		return "unknown afi"

	def pack (self):
		return pack('!H',self)

	@staticmethod
	def value (name):
		if name == "ipv4": return AFI.ipv4
		if name == "ipv6": return AFI.ipv6
		return None

# =================================================================== SAFI

# http://www.iana.org/assignments/safi-namespace
class SAFI (int):
	unicast_multicast = 0       # internal
	unicast = 1                 # [RFC4760]
	multicast = 2               # [RFC4760]
#	deprecated = 3              # [RFC4760]
	nlri_mpls = 4               # [RFC3107]
#	mcast_vpn = 5               # [draft-ietf-l3vpn-2547bis-mcast-bgp] (TEMPORARY - Expires 2008-06-19)
#	pseudowire = 6              # [draft-ietf-pwe3-dynamic-ms-pw] (TEMPORARY - Expires 2008-08-23) Dynamic Placement of Multi-Segment Pseudowires
#	encapsulation = 7           # [RFC5512]
#
#	tunel = 64                  # [Nalawade]
#	vpls = 65                   # [RFC4761]
#	bgp_mdt = 66                # [Nalawade]
#	bgp_4over6 = 67             # [Cui]
#	bgp_6over4 = 67             # [Cui]
#	vpn_adi = 69                # [RFC-ietf-l1vpn-bgp-auto-discovery-05.txt]
#
	mpls_vpn = 128              # [RFC4364]
#	mcast_bgp_mpls_vpn = 129    # [RFC2547]
#	rt = 132                    # [RFC4684]
	flow_ip = 133               # [RFC5575]
	flow_vpn = 134              # [RFC5575]
#
#	vpn_ad = 140                # [draft-ietf-l3vpn-bgpvpn-auto]
#
#	private = [_ for _ in range(241,254)]   # [RFC4760]
#	unassigned = [_ for _ in range(8,64)] + [_ for _ in range(70,128)]
#	reverved = [0,3] + [130,131] + [_ for _ in range(135,140)] + [_ for _ in range(141,241)] + [255,]    # [RFC4760]

	def name (self):
		if self == 0x01: return "unicast"
		if self == 0x02: return "multicast"
		if self == 0x04: return "nlri-mpls"
		if self == 0x80: return "mpls-vpn"
		if self == 0x85: return "flow"
		if self == 0x86: return "flow-vpn"
		return "unknown safi"

	def __str__ (self):
		return self.name()

	def pack (self):
		return chr(self)

	def has_label (self):
		return self in (self.nlri_mpls,self.mpls_vpn)

	def has_rd (self):
		return self in (self.mpls_vpn,)  # technically self.flow_vpn has an RD but it is not an NLRI

	@staticmethod
	def value (name):
		if name == "unicast"  : return 0x01
		if name == "multicast": return 0x02
		if name == "nlri-mpls": return 0x04
		if name == "mpls-vpn" : return 0x80
		if name == "flow"     : return 0x85
		if name == "flow-vpn" : return 0x86
		return None

def known_families ():
	# it can not be a generator
	families = []
	families.append((AFI(AFI.ipv4),SAFI(SAFI.unicast)))
	families.append((AFI(AFI.ipv4),SAFI(SAFI.multicast)))
	families.append((AFI(AFI.ipv4),SAFI(SAFI.nlri_mpls)))
	families.append((AFI(AFI.ipv4),SAFI(SAFI.mpls_vpn)))
	families.append((AFI(AFI.ipv4),SAFI(SAFI.flow_ip)))
	families.append((AFI(AFI.ipv4),SAFI(SAFI.flow_vpn)))
	families.append((AFI(AFI.ipv6),SAFI(SAFI.unicast)))
	families.append((AFI(AFI.ipv6),SAFI(SAFI.mpls_vpn)))
	families.append((AFI(AFI.ipv6),SAFI(SAFI.flow_ip)))
	families.append((AFI(AFI.ipv6),SAFI(SAFI.flow_vpn)))
	return families
