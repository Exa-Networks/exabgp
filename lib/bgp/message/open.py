#!/usr/bin/env python
# encoding: utf-8
"""
open.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009 Exa Networks. All rights reserved.
"""

from bgp.structure.family  import *
from bgp.structure.network import *
from bgp.structure.message import *

class Open (Message):
	TYPE = chr(0x01)

	def __init__ (self,version,asn,router_id,capabilities,hold_time):
		self.version = Version(version)
		self.asn = ASN(asn)
		self.hold_time = HoldTime(hold_time)
		self.router_id = RouterID(router_id)
		self.capabilities = capabilities

	def message (self):
		return self._message("%s%s%s%s%s" % (self.version.pack(),self.asn.pack(),self.hold_time.pack(),self.router_id.pack(),chr(0)))

	def __str__ (self):
		return "OPEN version=%d asn=%d hold_time=%s router_id=%s capabilities=[%s]" % (self.version, self.asn, self.hold_time, self.router_id,self.capabilities)

# =================================================================== Version

class Version (int):
	def pack (self):
		return chr(self)

# =================================================================== HoldTime

class HoldTime (int):
	def pack (self):
		return pack('!H',self)

	def keepalive (self):
		return int(self/3)

	def __len__ (self):
		return 2

# =================================================================== RouterID

class RouterID (IP):
	pass

# =================================================================== Parameter

class Parameter (int):
	AUTHENTIFICATION_INFORMATION = 0x01 # Depreciated
	CAPABILITIES                 = 0x02

	def __str__ (self):
		if self == 0x01: return "AUTHENTIFICATION INFORMATION"
		if self == 0x02: return "OPTIONAL"
		return 'UNKNOWN'

# =================================================================== Capabilities

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

	_unassigned = range(70,128)
	_reserved = range(128,256)

	def __str__ (self):
		r = []
		for key in self.keys():
			if key == self.MULTIPROTOCOL_EXTENSIONS:
				r += ['Multiprotocol for ' + ' '.join(["%s %s" % (str(afi),str(safi)) for (afi,safi) in self[key]])]
			elif key == self.ROUTE_REFRESH:
				r += ['Route Refresh']
			elif key == self.GRACEFUL_RESTART:
				r += ['Graceful Restart']
			elif key == self.FOUR_BYTES_ASN:
				r += ['4Bytes AS %d' % self[key]]
			elif key in self._reserved:
				r += ['private use capability %d' % key]
			elif key in self._unassigned:
				r += ['unassigned capability %d' % key]
			else:
				r+= ['unhandled capability %d' % key]
		return ', '.join(r)

	def default (self):
		self[1] = ((AFI(AFI.ipv4),SAFI(SAFI.unicast)),(AFI(AFI.ipv6),SAFI(SAFI.unicast)))
		return self

	def pack (self):
		rs = []
		for k,vs in self.iteritems():
			for v in vs:
				if k == self.MULTIPROTOCOL_EXTENSIONS:
					d = pack('!H',v[0]) + pack('!H',v[1])
					rs.append("%s%s%s" % (chr(k),chr(len(d)),d))
				else:
					rs.append("%s%s%s" % (chr(k),chr(len(v)),v))
		return "".join(["%s%s%s" % (chr(2),chr(len(r)),r) for r in rs])


