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
			raise ValueError('Invalid IP %s' % data)
	size = int(math.ceil(float(netmask)/8))
	return NLRI("%s%s" % (nm,pack[:size]),afi,SAFI.unicast)

def to_IP4 (value):
	return to_NLRI(value,32)

def to_IP6 (value):
	return to_NLRI(value,128)

def to_IP (value):
	return to_NLRI(value,128 if value.count(':') else 32)

class NLRI (object):
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
		return self._cache()[0]

	def mask (self):
		return self._cache()[1]

#	def nlri (self):
#		size = int(math.ceil(float(mask)/8))+1
#		return NLRI('%s%s' % (chr(size),self._pack[1:size]) ,AFI.ipv4,SAFI.unicast)

	def pack (self):
		return self.raw

	def packedip (self):
		if self.afi == AFI.ipv4:
			return self.raw[1:] + '\0'*(5-len(self.raw))
		return self.raw[1:] + '\0'*(17-len(self.raw))
		
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

