#!/usr/bin/env python
# encoding: utf-8
"""
network.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009 Exa Networks. All rights reserved.
"""

import math
import socket
from struct import *

from bgp.utils import *

# =================================================================== Protocol

# http://www.iana.org/assignments/protocol-numbers/
class Protcol (int):
	ICMP  = 0x01
	TCP   = 0x06
	UDP   = 0x11
	SCTP  = 0x84
	
	def __str__ (self):
		if self == 0x01: return "ICMP"
		if self == 0x06: return "TCP"
		if self == 0x11: return "UDP"
		if self == 0x84: return "SCTP"
		return "unknown protocol"

	def pack (self):
		return chr(self)


# =================================================================== ICMP Code Field

# http://www.iana.org/assignments/protocol-numbers/
class ICMP (int):
	ECHO_REPLY               = 0x00
	DESTINATION_UNREACHEABLE = 0x03
	SOURCE_QUENCH            = 0x04
	REDIRECT                 = 0x05
	ECHO                     = 0x08
	TIME_EXCEEDED            = 0x0B
	TRACEROUTE               = 0x1E

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
	nlri_mpls = 4				# [RFC3107]
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
	mpls_vpn = 128				# [RFC4364]
#	mcast_bgp_mpls_vpn = 129	# [RFC2547]
#	rt = 132					# [RFC4684]
	flow_ipv4 = 133				# [RFC5575]
	flow_vpnv4 = 134			# [RFC5575]
#
#	vpn_ad = 140				# [draft-ietf-l3vpn-bgpvpn-auto]
#
#	private = [_ for _ in range(241,254)]	# [RFC4760]
#	unassigned = [_ for _ in range(8,64)] + [_ for _ in range(70,128)]
#	reverved = [0,3] + [130,131] + [_ for _ in range(135,140)] + [_ for _ in range(141,241)] + [255,]	# [RFC4760]

	def __str__ (self):
		if self == 0x01: return "unicast"
		if self == 0x02: return "multicast"
		if self == 0x85: return "flow-ipv4"
		if self == 0x86: return "flow-vpnv4"
		return "unknown safi"

	def pack (self):
		return chr(self)

# =================================================================== IP

def to_IPv4 (ip):
	pack = socket.inet_pton(socket.AF_INET,ip)
	return IP(pack,AFI.ipv4,SAFI.unicast,ip)

def to_IPv6 (ip):
	pack = socket.inet_pton(socket.AF_INET6,ip)
	return IP(pack,AFI.ipv6,SAFI.unicast,ip)

def to_IP (value):
	if value.count(':'):
		return to_IPv6(value)
	return to_IPv4(value)

class IP (object):
	_af = {
		AFI.ipv4: socket.AF_INET,
		AFI.ipv6: socket.AF_INET6,
	}

	def __init__ (self,pip,afi,safi,ip=None):
		self.afi = afi
		self.safi = safi
		self.pip = pip
		self._ip = ip

	def ip (self):
		if not self._ip:
			if self.afi == AFI.ipv4:
				self._ip = socket.inet_ntop(self._af[self.afi],self.pip)
			else:
				self._ip = socket.inet_ntop(self._af[self.afi],self.pip)
		return self._ip

	def pack (self):
		return self.pip

	def packed (self):
		if self.afi == AFI.ipv4:
			return self.pip[1:] + '\0'*(5-len(self.pip))
		return self.pip[1:] + '\0'*(17-len(self.pip))

	def __str__ (self):
		return "%s" % self.ip()

	def __len__ (self):
		return len(self.pip)

	def __eq__ (self,other):
		if type(self) == type(other):
			return self.pip == other.pip and self.afi == other.afi and self.safi == other.safi
		# XXX: Should we implement the other test to not create bad surprised ? ...
		if type(other) != type(None):
			import warnings
			warnings.warn('we should never compare things which are not comparable %s and %s' % (type(self),type(other)))
		return False


# =================================================================== NLRI

def new_NLRI (data,afi=AFI.ipv4,safi=SAFI.unicast):
	size = int(math.ceil(float(ord(data[0]))/8)) + 1
	return NLRI(data[:size],afi,safi)

def to_NLRI(ip,netmask):
	try:
		nm = chr(int(netmask))
	except ValueError:
		raise ValueError('Invalid Netmask %s' % str(netmask))
	try:
		pack = socket.inet_pton(socket.AF_INET,ip)
		afi = AFI.ipv4
	except socket.error:
		try:
			pack = socket.inet_pton(socket.AF_INET6,ip)
			afi = AFI.ipv6
		except socket.error:
			raise ValueError('Invalid IP %s' % ip)
	size = int(math.ceil(float(netmask)/8))
	return NLRI("%s%s" % (nm,pack[:size]),afi,SAFI.unicast)

class NLRI (IP):
	_af = {
		AFI.ipv4: socket.AF_INET,
		AFI.ipv6: socket.AF_INET6,
	}

	def __init__ (self,raw,afi,safi):
		self.afi = afi
		self.safi = safi
		self.raw = raw
		self._ip = None
		self._mask = None

	def _cache (self):
		if not self._ip:
			if self.afi == AFI.ipv4:
				self._ip = socket.inet_ntop(self._af[self.afi],self.raw[1:] + '\0'*(5-len(self.raw)))
			else:
				self._ip = socket.inet_ntop(self._af[self.afi],self.raw[1:] + '\0'*(17-len(self.raw)))
			self._mask = ord(self.raw[0])
		return self._ip, self._mask

	def ip (self):
		if self.afi == AFI.ipv4: l = 5
		else: l = 17
		return IP(self.raw[1:] + '\0'*(l-len(self.raw)),self.api,self.safi)

	def mask (self):
		return ord(self.raw[0])

	def pack (self):
		return self.raw

	def __cmp__ (self,other):
		return \
			self.afi == other.afi and \
			self.safi == other.safi and \
			self.raw == other.raw

	def __str__ (self):
		return "%s/%d" % self._cache()

	def __len__ (self):
		return len(self.raw)

	def __eq__ (self,other):
		if type(self) == type(other):
			return self.raw == other.raw and self.afi == other.afi
		# XXX: Should we implement the other test to not create bad surprised ? ...
		if type(other) != type(None):
			import warnings
			warnings.warn('we should never compare things which are not comparable %s and %s' % (type(self),type(other)))
		return False

#		return int(math.ceil(float(self.mask)/8)) + 1

# =================================================================== Family

class Family (object):
	def __init__ (self,afi,safi):
		self.afi = AFI(afi)
		self.safi = SAFI(safi)

	def format (self):
		if afi in (AFI.ipv4,AFI.ipv6) and safi in (SAFI.unicast,): return NLRI

# =================================================================== ASN

def to_ASN (data):
	return ASN(int(data))

class ASN (int):
	# regex = "(?:0[xX][0-9a-fA-F]{1,8}|\d+:\d+|\d+)"
	length = 2

	def four (self):
		self.length = 4
		return self

	def pack (self):
		if self.length == 2:
			return pack('!H',self)
		return pack('!L',self)

	def __len__ (self):
		return self.length

