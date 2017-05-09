# encoding: utf-8
"""
family.py

Created by Thomas Mangin on 2010-01-19.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

from struct import pack
from struct import unpack

from exabgp.util import character
from exabgp.util import ordinal
from exabgp.protocol.resource import Resource

# ======================================================================== AFI
# https://www.iana.org/assignments/address-family-numbers/


class AFI (Resource):
	undefined = 0x00  # internal
	ipv4      = 0x01
	ipv6      = 0x02
	l2vpn     = 0x19
	bgpls     = 0x4004

	# Family = {
	# 	ipv4:  0x02,  # socket.AF_INET,
	# 	ipv6:  0x30,  # socket.AF_INET6,
	# 	l2vpn: 0x02,  # l2vpn info over ipv4 session
	# }

	codes = dict ((k.lower().replace('_','-'),v) for (k,v) in {
		'ipv4':  ipv4,
		'ipv6':  ipv6,
		'l2vpn': l2vpn,
		'bgpls': bgpls,
	}.items())

	names = dict([(r,l) for (l,r) in codes.items()])
	inet_names = dict([(r,l.replace('ipv','inet')) for (l,r) in codes.items()])

	masks = {
		ipv4:  32,
		ipv6:  128,
	}

	def __str__ (self):
		return self.names.get(self,"unknown afi %d" % int(self))

	def __repr__ (self):
		return str(self)

	def mask (self):
		return self.masks.get(self,'invalid request for this family')

	def name (self):
		return self.inet_names.get(self,"unknown afi")

	def pack (self):
		return pack('!H',self)

	@staticmethod
	def unpack (data):
		return AFI(unpack('!H',data)[0])

	@classmethod
	def value (cls,name):
		return cls.codes.get(name,None)

	@staticmethod
	def implemented_safi (afi):
		if afi == 'ipv4':
			return ['unicast','multicast','nlri-mpls','mpls-vpn','flow','flow-vpn']
		if afi == 'ipv6':
			return ['unicast','mpls-vpn','flow','flow-vpn']
		if afi == 'l2vpn':
			return ['vpls','evpn']
		if afi == 'bgpls':
			return ['bgp-ls','bgp-ls-vpn']
		return []

	@classmethod
	def fromString (cls, string):
		return cls.codes.get(string,cls.undefined)


# ======================================================================= SAFI

# https://www.iana.org/assignments/safi-namespace
class SAFI (Resource):
	undefined = 0               # internal
	unicast = 1                 # [RFC4760]
	multicast = 2               # [RFC4760]
	# deprecated = 3            # [RFC4760]
	nlri_mpls = 4               # [RFC3107]
	# mcast_vpn = 5             # [draft-ietf-l3vpn-2547bis-mcast-bgp] (TEMPORARY - Expires 2008-06-19)
	# pseudowire = 6            # [draft-ietf-pwe3-dynamic-ms-pw] (TEMPORARY - Expires 2008-08-23) Dynamic Placement of Multi-Segment Pseudowires
	# encapsulation = 7         # [RFC5512]

	# tunel = 64                # [Nalawade]
	vpls = 65                   # [RFC4761]
	# bgp_mdt = 66              # [Nalawade]
	# bgp_4over6 = 67           # [Cui]
	# bgp_6over4 = 67           # [Cui]
	# vpn_adi = 69              # [RFC-ietf-l1vpn-bgp-auto-discovery-05.txt]

	evpn = 70                   # [draft-ietf-l2vpn-evpn]
	bgp_ls = 71                 # [RFC7752]
	bgp_ls_vpn = 72             # [RFC7752]
	mpls_vpn = 128              # [RFC4364]
	# mcast_bgp_mpls_vpn = 129  # [RFC2547]
	# rt = 132                  # [RFC4684]
	rtc = 132                   # [RFC4684]
	flow_ip = 133               # [RFC5575]
	flow_vpn = 134              # [RFC5575]

	# vpn_ad = 140              # [draft-ietf-l3vpn-bgpvpn-auto]

	# private = [_ for _ in range(241,254)]   # [RFC4760]
	# unassigned = [_ for _ in range(8,64)] + [_ for _ in range(70,128)]
	# reverved = [0,3] + [130,131] + [_ for _ in range(135,140)] + [_ for _ in range(141,241)] + [255,]    # [RFC4760]

	codes = {
		'unicast':   unicast,
		'multicast': multicast,
		'nlri-mpls': nlri_mpls,
		'vpls':      vpls,
		'evpn':      evpn,
		'bgp-ls':    bgp_ls,
		'bgp-ls-vpn':bgp_ls_vpn,
		'mpls-vpn':  mpls_vpn,
		'rtc':       rtc,
		'flow':      flow_ip,
		'flow-vpn':  flow_vpn,
	}

	names = dict([(r,l) for (l,r) in codes.items()])

	def name (self):
		return self.names.get(self,'unknown safi %d' % int(self))

	def __str__ (self):
		return self.name()

	def __repr__ (self):
		return str(self)

	def pack (self):
		return character(self)

	@staticmethod
	def unpack (data):
		return SAFI(ordinal(data))

	def has_label (self):
		return self in (self.nlri_mpls,self.mpls_vpn)

	def has_rd (self):
		return self in (self.mpls_vpn,)  # technically self.flow_vpn and self.vpls has an RD but it is not an NLRI

	@classmethod
	def value (cls,name):
		return cls.codes.get(name,None)

	@classmethod
	def fromString (cls, string):
		return cls.codes.get(string,cls.undefined)


# ===================================================================== FAMILY


class Family (object):
	__slots__ = ['afi','safi']

	def __init__ (self, afi, safi):
		self.afi = AFI(afi)
		self.safi = SAFI(safi)

	def has_label (self):
		if self.safi in (SAFI.nlri_mpls,SAFI.mpls_vpn):
			return True
		return False

	def has_rd (self):
		if self.safi in (SAFI.nlri_mpls,SAFI.mpls_vpn,SAFI.flow_vpn):
			return True
		return False

	def __eq__ (self, other):
		return \
			self.afi == other.afi and \
			self.safi == other.safi

	def __neq__ (self, other):
		return \
			self.afi != other.afi or \
			self.safi != other.safi

	def __lt__ (self, other):
		raise RuntimeError('comparing Family for ordering does not make sense')

	def __le__ (self, other):
		raise RuntimeError('comparing Family for ordering does not make sense')

	def __gt__ (self, other):
		raise RuntimeError('comparing Family for ordering does not make sense')

	def __ge__ (self, other):
		raise RuntimeError('comparing Family for ordering does not make sense')

	def family (self):
		return (self.afi,self.safi)

	def extensive (self):
		return 'afi %s safi %s' % (self.afi,self.safi)

	def __repr__ (self):
		return "%s %s" % (str(self.afi),str(self.safi))
