# encoding: utf-8
"""
open.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2012 Exa Networks. All rights reserved.
"""

import os
import socket
from struct import pack

from exabgp.structure.address import AFI,SAFI
from exabgp.structure.asn  import ASN
from exabgp.message import Message

# =================================================================== Open

class Open (Message):
	TYPE = chr(0x01)

	def __init__ (self,version,asn,router_id,capabilities,hold_time):
		self.version = Version(version)
		self.asn = ASN(asn)
		self.hold_time = HoldTime(hold_time)
		self.router_id = RouterID(router_id)
		self.capabilities = capabilities

	def message (self):
		if self.asn.asn4():
			return self._message("%s%s%s%s%s" % (self.version.pack(),ASN(23456).pack(False),self.hold_time.pack(),self.router_id.pack(),self.capabilities.pack()))
		return self._message("%s%s%s%s%s" % (self.version.pack(),self.asn.pack(False),self.hold_time.pack(),self.router_id.pack(),self.capabilities.pack()))

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

class RouterID (object):
	def __init__ (self,ip):
		self.ip = ip
		try:
			self.raw = socket.inet_pton(socket.AF_INET,ip)
		except socket.error:
			raise ValueError('invalid IP address %s' % str(ip))

	def afi (self):
		return AFI.ipv4

	def __len__ (self):
		return 4

	def pack (self):
		return self.raw

	def __str__ (self):
		return self.ip

	def __repr__ (self):
		return str(self)

	def __eq__ (self,other):
		return self.ip == other.ip

# =================================================================== Graceful (Restart)
# RFC 4727

class Graceful (dict):
	TIME_MASK     = 0x0FFF
	FLAG_MASK     = 0xF000

	# 0x8 is binary 1000
	RESTART_STATE = 0x08
	FORWARDING_STATE = 0x80

	def __init__ (self,restart_flag,restart_time,protos):
		dict.__init__(self)
		self.restart_flag = restart_flag
		self.restart_time = restart_time & Graceful.TIME_MASK
		for afi,safi,family_flag in protos:
			self[(afi,safi)] = family_flag & Graceful.FORWARDING_STATE

	def extract (self):
		restart  = pack('!H',((self.restart_flag << 12) | (self.restart_time & Graceful.TIME_MASK)))
		families = [(afi.pack(),safi.pack(),chr(self[(afi,safi)])) for (afi,safi) in self.keys()]
		sfamilies = ''.join(["%s%s%s" % (pafi,psafi,family) for (pafi,psafi,family) in families])
		return ["%s%s" % (restart,sfamilies)]

	def __str__ (self):
		families = [(str(afi),str(safi),hex(self[(afi,safi)])) for (afi,safi) in self.keys()]
		sfamilies = ' '.join(["%s/%s=%s" % (afi,safi,family) for (afi,safi,family) in families])
		return "Graceful Restart Flags %s Time %d %s" % (hex(self.restart_flag),self.restart_time,sfamilies)

	def families (self):
		return self.keys()

# =================================================================== MultiProtocol

class MultiProtocol (list):
	def __str__ (self):
		return 'Multiprotocol ' + ' '.join(["%s %s" % (safi,ssafi) for (safi,ssafi) in [(str(afi),str(safi)) for (afi,safi) in self]])

	def extract (self):
		rs = []
		for v in self:
			rs.append(pack('!H',v[0]) + pack('!H',v[1]))
		return rs

# =================================================================== MultiSession

class MultiSession (list):
	def __str__ (self):
		return 'Multisession %s' % ' '.join([str(capa) for capa in self])

	def extract (self):
		rs = [chr(0),]
		for v in self:
			rs.append(chr(v))
		return  rs

# =================================================================== RouteRefresh

class RouteRefresh (list):
	def __str__ (self):
		return "Route Refresh (unparsed)"

	def extract (self):
		return []

class CiscoRouteRefresh (list):
	def __str__ (self):
		return "Cisco Route Refresh (unparsed)"

	def extract (self):
		return []

# =================================================================== Parameter

class ASN4 (int):
	def extract (self):
		return [pack('!L',self)]

# =================================================================== Unknown

class Unknown (object):
	def __init__ (self,value,raw=''):
		self.value = value
		self.raw = raw

	def __str__ (self):
		if self.value in Capabilities.reserved: return 'Reserved %s' % str(self.value)
		if self.value in Capabilities.unassigned: return 'Unassigned %s' % str(self.value)
		return 'unknown %s %s' % (str(self.value),str(self.raw))

	def extract (self):
		return []

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
	MULTISESSION_BGP_RFC     = 0x44 # [draft-ietf-idr-bgp-multisession]
	ADD_PATH                 = 0x45 # [draft-ietf-idr-add-paths]
	# 70-127    Unassigned
	CISCO_ROUTE_REFRESH      = 0x80 # I Can only find reference to this in the router logs
	# 128-255   Reserved for Private Use [RFC5492]
	MULTISESSION_BGP         = 0x83 # What Cisco really use for Multisession (yes this is a reserved range in prod !)

	EXTENDED_MESSAGE         = -1 # No yet defined by draft http://tools.ietf.org/html/draft-ietf-idr-extended-messages-02.txt

	unassigned = range(70,128)
	reserved = range(128,256)

	def announced (self,capability):
		return self.has_key(capability)

	# XXX: Should we not call the __str__ function of all the created capability classes ?
	def __str__ (self):
		r = []
		for key in self.keys():
			if key == self.MULTIPROTOCOL_EXTENSIONS:
				r += [str(self[key])]
			elif key == self.ROUTE_REFRESH:
				r += ['Route Refresh']
			elif key == self.CISCO_ROUTE_REFRESH:
				r += ['Cisco Route Refresh']
			elif key == self.GRACEFUL_RESTART:
				r += ['Graceful Restart']
			elif key == self.FOUR_BYTES_ASN:
				r += ['4Bytes AS %d' % self[key]]
			elif key == self.MULTISESSION_BGP:
				r += [str(self[key])]
			elif key == self.MULTISESSION_BGP_RFC:
				r += ['Multi Session']
			elif key in self.reserved:
				r += ['private use capability %d' % key]
			elif key in self.unassigned:
				r += ['unassigned capability %d' % key]
			else:
				r += ['unhandled capability %d' % key]
		return ', '.join(r)

	def default (self,neighbor,restarted):
		graceful = neighbor.graceful_restart

		if neighbor.multisession or os.environ.get('MINIMAL_MP','0') in ['','1','yes','Yes','YES']:
			families = neighbor.families()
		else:
			families = []
			families.append((AFI(AFI.ipv4),SAFI(SAFI.unicast)))
			families.append((AFI(AFI.ipv6),SAFI(SAFI.unicast)))
			families.append((AFI(AFI.ipv4),SAFI(SAFI.flow_ipv4)))

		mp = MultiProtocol()
		mp.extend(families)
		self[Capabilities.MULTIPROTOCOL_EXTENSIONS] = mp
		self[Capabilities.FOUR_BYTES_ASN] = ASN4(neighbor.local_as)

		if graceful:
			if restarted:
				self[Capabilities.GRACEFUL_RESTART] = Graceful(Graceful.RESTART_STATE,graceful,[(afi,safi,Graceful.FORWARDING_STATE) for (afi,safi) in families])
			else:
				self[Capabilities.GRACEFUL_RESTART] = Graceful(0x0,graceful,[(afi,safi,Graceful.FORWARDING_STATE) for (afi,safi) in families])

		# MUST be the last key added
		if neighbor.multisession:
			self[Capabilities.MULTISESSION_BGP] = MultiSession([Capabilities.MULTIPROTOCOL_EXTENSIONS])
		return self

	def pack (self):
		rs = []
		for k,capabilities in self.iteritems():
			for capability in capabilities.extract():
				rs.append("%s%s%s" % (chr(k),chr(len(capability)),capability))
		parameters = "".join(["%s%s%s" % (chr(2),chr(len(r)),r) for r in rs])
		return "%s%s" % (chr(len(parameters)),parameters)
