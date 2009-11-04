#!/usr/bin/env python
# encoding: utf-8
"""
data.py

Created by Thomas Mangin on 2009-08-25.
Copyright (c) 2009 Exa Networks. All rights reserved.
"""

HOLD_TIME=180

import math
import time
import socket
from struct import pack,unpack
	# !L : Network Long  (4 bytes)
	# !H : Network Short (2 bytes)

CAFE = chr(202) + chr(254)

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
		if self == 1: return "unicast"
		if self == 2: return "multicast"
		return "unknown safi"

	def pack (self):
		return chr(self)

class IP (object):
	def __init__ (self,value):
		v4 = False
		try:
			pack = socket.inet_pton(socket.AF_INET, str(value))
			numeric = unpack('>L',pack)[0]
			string = str(value)
			v4 = True
		except socket.error:
			pass
		except TypeError:
			pass

		if not v4:
			try:
				pack = socket.inet_pton(socket.AF_INET6, str(value))
				a,b,c,d = unpack('>LLLL',pack)
				numeric = (a << 96) + (b << 64) + (c << 32) + d
				string = str(value).lower()
			except socket.error:
				raise ValueError('"%s" is an invalid address' % str(value))
			except TypeError:
				raise ValueError('"%s" is an invalid address' % str(value))

		self.numeric = numeric
		self._pack = pack
		self.string = string

		if v4:
			self.version = 4
			self.length = 32
		else:
			self.version = 6
			self.length = 128

	def pack (self):
		return self._pack

	def __str__ (self):
		return self.string

	def __len__ (self):
		return self.version

# Super sub-optimal as code... make length as parameter of __init__ ?
class Mask (int):
	def new (self,mask,length):
		#slash_to_size = dict([(length-bits,(1<<bits)) for bits in range(0,length+1)])
		#slash_to_mask = dict([(length-bits,(1L<<length) - (1<<bits)) for bits in range(0,length+1)])
		mask_to_slash = dict([((1L<<length) - (1<<bits),length-bits) for bits in range(0,length+1)])
		ipv4_to_slash = dict([("%d.%d.%d.%d" % (k>>24, k>>16 & 0xFF ,k>>8 & 0xFF, k&0xFF),mask_to_slash[k]) for k in mask_to_slash.keys()])

		#regex_mask = '(?:\d|[12]\d|3[012])'
		try:
			slash = int(mask)
		except ValueError:
			try:
				slash = self.ipv4_to_slash[mask]
			except KeyError:
				raise ValueError('the netmask is invalid %s' % str(mask))

		if not slash in range(0,length+1):
			return ValueError('the netmask is invalid /%s' % str(slash))

		return Mask(slash)

	def pack (self):
		return chr(self)

	def __len__ (self):
		return 1

class RouterID (IP):
	pass

class Version (int):
	def pack (self):
		return chr(self)

class ASN (int):
	# regex = "(?:0[xX][0-9a-fA-F]{1,8}|\d+:\d+|\d+)"

	def __init__ (self,value):
		int.__init__(self,value)
		self.length = 2
	
	def four (self):
		self.length = 4
		return self
	
	def pack (self):
		if self.length == 2:
			return pack('!H',self)
		return pack('!L',self)

	def __len__ (self):
		return self.length
	
class Community (long):
	def new (self,data):
		try:
			value = int(data)
		except ValueError:
			separator = data.find(':')
			if separator > 0:
				value = (long(data[:separator])<<16) + long(data[separator+1:])
			elif len(data) >=2 and data[1] in 'xX':
				value = long(data,16)
			else:
				value = long(data)
		return Community(value)

	def pack (self):
		return pack('!L',self)

	def __str__ (self):
		return "%d:%d" % (self >> 16, self & 0xFFFF)

	def __len__ (self):
		return 4


class Communities (list):
	_factory = Community()
	
	def append (self,data):
		list.append(self,self._factory.new(data))
		self.sort()

	def pack (self):
		return ''.join([community.pack() for community in self])

	def __str__ (self):
		if len(self) >  1: return '[ %s ]' % ' '.join([str(community) for community in self])
		if len(self) == 1: return str(self[0])
		return ''

class LocalPreference (long):
	def pack (self):
		return pack('!L',self)

	def __len__ (self):
		return 4

class HoldTime (int):
	def pack (self):
		return pack('!H',self)

	def keepalive (self):
		return int(self/3)

	def __len__ (self):
		return 2

class Flag (int):
	EXTENDED_LENGTH = 0x10 # 16
	PARTIAL         = 0x20 # 32
	TRANSITIVE      = 0x40 # 64
	OPTIONAL        = 0x80 # 128

	def __str__ (self):
		r = []
		v = int(self)
		if v & 0x10:
			r.append("EXTENDED_LENGTH")
			v -= 0x10
		if v & 0x20:
			r.append("PARTIAL")
			v -= 0x20
		if v & 0x40:
			r.append("TRANSITIVE")
			v -= 0x40
		if v & 0x80:
			r.append("OPTIONAL")
			v -= 0x80
		if v:
			r.append("UNKNOWN %s" % hex(v))
		return " ".join(r)

class Origin (int):
	IGP        = 0x00
	EGP        = 0x01
	INCOMPLETE = 0x02

	def __str__ (self):
		if self == 0x00: return 'IGP'
		if self == 0x01: return 'EGP'
		if self == 0x02: return 'INCOMPLETE'
		return 'INVALID'

	def pack (self):
		return chr(self)

class ASPath (int):
	AS_SET      = 0x01
	AS_SEQUENCE = 0x02

	def __str__ (self):
		if self == 0x01: return 'AS_SET'
		if self == 0x02: return 'AS_SEQUENCE'
		return 'INVALID'

class Attribute (int):
	# RFC 4271
	ORIGIN           = 0x01
	AS_PATH          = 0x02
	NEXT_HOP         = 0x03
	MULTI_EXIT_DISC  = 0x04
	LOCAL_PREFERENCE = 0x05
	ATOMIC_AGGREGATE = 0x06
	AGGREGATOR       = 0x07
	COMMUNITY        = 0x08
	# RFC 4760
	MP_REACH_NLRI    = 0x0e # 14
	MP_UNREACH_NLRI  = 0x0f # 15

	def __str__ (self):
		if self == 0x01: return "ORIGIN"
		if self == 0x02: return "AS_PATH"
		if self == 0x03: return "NEXT_HOP"
		if self == 0x04: return "MULTI_EXIT_DISC"
		if self == 0x05: return "LOCAL_PREFERENCE"
		if self == 0x06: return "ATOMIC_AGGREGATE"
		if self == 0x07: return "AGGREGATOR"
		if self == 0x08: return "COMMUNITY"
		if self == 0x0e: return "MP_REACH_NLRI"
		if self == 0x0f: return "MP_UNREACH_NLRI"
		return 'UNKNOWN'

class Parameter (int):
	AUTHENTIFICATION_INFORMATION = 0x01 # Depreciated
	CAPABILITIES                 = 0x02

	def __str__ (self):
		if self == 0x01: return "AUTHENTIFICATION INFORMATION"
		if self == 0x02: return "OPTIONAL"
		return 'UNKNOWN'

# http://www.iana.org/assignments/capability-codes/
class Capabilities (dict):
	RESERVED                 = 0x00 # [RFC5492]
	MULTIPROTOCOL_EXTENSIONS = 0x01 # [RFC2858]
	ROUTE_REFRESH            = 0x02 # [RFC2918]
	OUTBOUND_ROUTE_FILTERING = 0x03 # [RFC5291]
	MULTIPLE_ROUTES          = 0x04 # [RFC3107]
	EXTENDED_NEXT_HOP        = 0x05 # [RFC5549]
	#6-63      Unassigned
	GRACEFUL_RESTART         = 0x40 # [RFC4724]
	FOUR_BYTES_ASN           = 0x41 # [RFC4893]
	# 66 Deprecated
	DYNAMIC_CAPABILITY       = 0x43 # [Chen]
	MULTISESSION_BGP         = 0x44 # [Appanna]
	ADD_PATH                 = 0x45 # [draft-ietf-idr-add-paths]
	# 70-127    Unassigned 
	# 128-255   Reserved for Private Use [RFC5492]

	def __str__ (self):
		r = []
		for key in self.keys():
			if key == self.MULTIPROTOCOL_EXTENSIONS:
				r += ['Multiprotocol Reachable NLRI for ' + ' '.join(["%s %s" % (str(afi),str(safi)) for (afi,safi) in self[key]])]
			elif key == self.ROUTE_REFRESH:
				r += ['Route Refresh']
			elif key == self.GRACEFUL_RESTART:
				r += ['Graceful Restart']
			elif key == self.FOUR_BYTES_ASN:
				r += ['4Bytes AS %d' % self[key]]
			else:
				r+= ['unknown capability %d' % key]
		return ', '.join(r)

	def default (self):
		self[1] = ((AFI(AFI.ipv4),SAFI(SAFI.unicast)),(AFI(AFI.ipv6),SAFI(SAFI.unicast)))
		return self

	def pack (self):
		rs = []
		for k,vs in self.iteritems():
			for v in vs:
				if k == 1:
					d = pack('!H',v[0]) + pack('!H',v[1])
					rs.append("%s%s%s" % (chr(k),chr(len(d)),d))
				else:
					rs.append("%s%s%s" % (chr(k),chr(len(v)),v))
		return "".join(["%s%s%s" % (chr(2),chr(len(r)),r) for r in rs])

class Prefix (object):
	_factory = Mask()
	
	# format is (version,address,slash)
	def __init__ (self,address,mask):
		self.ip = IP(address)
		self.mask = self._factory.new(mask,self.ip.length)

	def bgp (self):
		size = int(math.ceil(float(self.mask)/8))
		return "%s%s" % (self.mask.pack(),self.ip.pack()[:size])

	def __str__ (self):
		return '%s/%d' % (self.ip,self.mask)

class Route (Prefix):
	def __init__ (self,ip,slash,next_hop=''):
		Prefix.__init__(self,ip,slash)
		self.next_hop = next_hop if next_hop else ip
		self.local_preference = 100
		self.communities = Communities()

	def get_next_hop (self):
		return self._next_hop
	def set_next_hop (self,ip):
		self._next_hop = IP(ip)
	next_hop = property(get_next_hop,set_next_hop)

	def get_local_preference (self):
		return self._local_preference
	def set_local_preference (self,preference):
		self._local_preference = LocalPreference(preference)
	local_preference = property(get_local_preference,set_local_preference)

	def __cmp__ (self,other):
		return \
			self.ip == other.ip and \
			self.mask == other.mask and \
			self.next_hop == other.next_hop and \
			self.local_preference == other.local_preference and \
			self.communities == other.communities

	def __str__ (self):
		return "%s next-hop %s%s%s" % \
		(
			Prefix.__str__(self),
			self.next_hop,
			" local_preference %d" % self.local_preference if self.local_preference != 100 else '',
			" community %s" % self.communities if self.communities else ''
		)

	def _attribute (self,attr_flag,attr_type,value):
		if attr_flag & Flag.OPTIONAL and not value:
			return ''
		length = len(value)
		if length > 0xFF:
			attr_flag &= Flag.EXTENDED_LENGTH
		if attr_flag & Flag.EXTENDED_LENGTH:
			len_value = pack('!H',length)[0]
		else:
			len_value = chr(length)
		return "%s%s%s%s" % (chr(attr_flag),chr(attr_type),len_value,value)

	def _segment (self,seg_type,values):
		if len(values)>255:
			return self._segment(values[:256]) + self._segment(values[256:])
		return "%s%s%s" % (chr(seg_type),chr(len(values)),''.join([v.pack() for v in values]))

	def pack (self,local_asn,peer_asn,mp_action=''):
		message = ''
		message += self._attribute(Flag.TRANSITIVE,Attribute.ORIGIN,Origin(Origin.IGP).pack())
		message += self._attribute(Flag.TRANSITIVE,Attribute.AS_PATH,'' if local_asn == peer_asn else self._segment(ASPath.AS_SEQUENCE,[local_asn]))
		if local_asn == peer_asn:
			message += self._attribute(Flag.TRANSITIVE,Attribute.LOCAL_PREFERENCE,self.local_preference.pack())
		message += self._attribute(Flag.TRANSITIVE|Flag.OPTIONAL,Attribute.COMMUNITY,''.join([c.pack() for c in self.communities])) if self.communities else ''
		# we do not store or send MED
		if self.ip.version == 4:
			message += self._attribute(Flag.TRANSITIVE,Attribute.NEXT_HOP,self.next_hop.pack())
		if self.ip.version == 6:
			if mp_action == '-':
				attr = AFI(AFI.ipv6).pack() + SAFI(SAFI.unicast).pack() + Prefix.pack(self)
				message += self._attribute(Flag.TRANSITIVE,Attribute.MP_UNREACH_NLRI,attr)
			if mp_action == '+':
				prefix = Prefix.bgp(self)
				next_hop = self.next_hop.pack()
				attr = AFI(AFI.ipv6).pack() + SAFI(SAFI.unicast).pack() + chr(len(next_hop)) + next_hop + chr(0) + prefix
				message += self._attribute(Flag.TRANSITIVE,Attribute.MP_REACH_NLRI,attr)
		return message

# The definition of a neighbor (from reading the configuration)

class Neighbor (object):
	def __init__ (self):
		self.description = ''
		self._router_id = None
		self.local_address = None
		self.peer_address = None
		self.peer_as = None
		self.local_as = None
		self.hold_time = HoldTime(HOLD_TIME)
		self.routes = []

	def missing (self):
		if self.local_address is None: return 'local-address'
		if self.peer_address is None: return 'peer-address'
		if self.local_as is None: return 'local-as'
		if self.peer_as is None: return 'peer-as'
		if self.peer_address.version == 6 and not self._router_id: return 'router-id'
		return ''


	def get_router_id (self):
		return self._router_id if self._router_id else self.local_address
	def set_router_id (self,id):
		self._router_id = id
	router_id = property(get_router_id,set_router_id)

	def __eq__ (self,other):
		return \
			self._router_id == other._router_id and \
			self.local_address == other.local_address and \
			self.local_as == other.local_as and \
			self.peer_address == other.peer_address and \
			self.peer_as == other.peer_as

	def __ne__(self, other):
		return not (self == other)

	def __str__ (self):
		return """\
neighbor %s {
	description "%s";
	router-id %s;
	local-address %s;
	local-as %d;
	peer-as %d;
	static {%s
	}
}""" % (
	self.peer_address,
	self.description,
	self.router_id,
	self.local_address,
	self.local_as,
	self.peer_as,
	'\n\t\t' + '\n\t\t'.join([str(route) for route in self.routes]) if self.routes else ''
)


# Taken from perl Net::IPv6Addr
#	ipv6_patterns = {
#		'preferred' : """\
#			^(?:[a-f0-9]{1,4}:){7}[a-f0-9]{1,4}$
#		""",
#		'compressed' : """\
#			^[a-f0-9]{0,4}::$
#		|	^:(?::[a-f0-9]{1,4}){1,6}$
#		|	^(?:[a-f0-9]{1,4}:){1,6}:$
#		|	^(?:[a-f0-9]{1,4}:)(?::[a-f0-9]{1,4}){1,6}$
#		|	^(?:[a-f0-9]{1,4}:){2}(?::[a-f0-9]{1,4}){1,5}$
#		|	^(?:[a-f0-9]{1,4}:){3}(?::[a-f0-9]{1,4}){1,4}$
#		|	^(?:[a-f0-9]{1,4}:){4}(?::[a-f0-9]{1,4}){1,3}$
#		|	^(?:[a-f0-9]{1,4}:){5}(?::[a-f0-9]{1,4}){1,2}$
#		|	^(?:[a-f0-9]{1,4}:){6}(?::[a-f0-9]{1,4})$
#		""",
#		'ipv4' : """\
#			^(?:0:){5}ffff:(?:\d{1,3}\.){3}\d{1,3}$
#		|	^(?:0:){6}(?:\d{1,3}\.){3}\d{1,3}$
#		""",
#		'ipv4 compressed' : """\
#			^::(?:ffff:)?(?:\d{1,3}\.){3}\d{1,3}$
#		""",
#	}
#
#	ipv4_patterns = '(?:\d{1,2}|1\d{2}|2[0-4]\d|25[0-5])\.(?:\d{1,2}|1\d{2}|2[0-4]\d|25[0-5])\.(?:\d{1,2}|1\d{2}|2[0-4]\d|25[0-5])\.(?:\d{1,2}|1\d{2}|2[0-4]\d|25[0-5])'


