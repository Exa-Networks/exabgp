#!/usr/bin/env python
# encoding: utf-8
"""
open.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009 Exa Networks. All rights reserved.
"""

from bgp.message.parent import *
from bgp.message.inet   import *

def new_Open (data):
	version = ord(data[0])
	if version != 4:
		# Only version 4 is supported nowdays..
		raise Notify(2,1,data[0])
	asn = unpack('!H',data[1:3])[0]
	hold_time = unpack('!H',data[3:5])[0]
	numeric = unpack('!L',data[5:9])[0]
	router_id = "%d.%d.%d.%d" % (numeric>>24,(numeric>>16)&0xFF,(numeric>>8)&0xFF,numeric&0xFF)
	capabilities = new_Capabilities(data[9:])
	return Open(version,asn,router_id,capabilities,hold_time)

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
		return self._message("%s%s%s%s%s" % (self.version.pack(),self.asn.pack(),self.hold_time.pack(),self.router_id.pack(),self.capabilities.pack()))

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
		self.raw = socket.inet_pton(socket.AF_INET,ip)

	def afi (self):
		return AFI.ipv4

	def __len__ (self):
		return 4

	def pack (self):
		return self.raw
	
	def __str__ (self):
		return self.ip

	def __cmp__ (self,other):
		if type(self) == type(other):
			return self.raw == other.raw
		if self.raw == other:
			return cmp(self.raw,other)
		return cmp(self.ip,other)

# =================================================================== Graceful (Restart)
# RFC 4727

class Graceful (dict):
	TIME_MASK     = 0x0FFF
	FLAG_MASK     = 0xF000

	# 0x8 is binary 1000
	RESTART_STATE = 0x08 
	FORWARDING_STATE = 0x80
	
	def __init__ (self,restart_flag,restart_time,protos):
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


# =================================================================== MultiProtocol

class MultiProtocol (list):
	def __str__ (self):
		return 'Multiprotocol ' + ' '.join(["%s %s" % (safi,ssafi) for (safi,ssafi) in [(str(afi),str(safi)) for (afi,safi) in self]])

	def extract (self):
		rs = []
		for v in self:
			rs.append(pack('!H',v[0]) + pack('!H',v[1]))
		return rs

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

# =================================================================== Unknown

class Unknown (object):
	def __init__ (self,value):
		self.value = value
	
	def __str__ (self):
		if self.value in Capabilities.reserved: return 'Reserved %s' % str(self.value)
		if self.value in Capabilities.unassigned: return 'Unassigned %s' % str(self.value)
		return 'unknown %s' % str(self.value)

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

def _key_values (name,data):
	if len(data) < 2:
		raise Notify(2,0,"bad length for OPEN %s (<2)" % name)
	l = ord(data[1])
	boundary = l+2
	if len(data) < boundary:
		raise Notify(2,0,"bad length for OPEN %s (buffer underrun)" % name)
	key = ord(data[0])
	value = data[2:boundary]
	rest = data[boundary:]
	return key,value,rest


def new_Capabilities (data):
	capabilities = Capabilities()
	option_len = ord(data[0])
	if option_len:
		data = data[1:]
		while data:
			key,value,data = _key_values('parameter',data)
			# Paramaters must only be sent once.
			if key == Parameter.AUTHENTIFICATION_INFORMATION:
				raise Notify(2,5)
				continue

			if key == Parameter.CAPABILITIES:
				k,v,r = _key_values('capability',value)
				if r:
					raise Notify(2,0,"bad length for OPEN %s (size mismatch)" % 'capability')

				if k == Capabilities.MULTIPROTOCOL_EXTENSIONS:
					if k not in capabilities:
						capabilities[k] = MultiProtocol()
					afi = AFI(unpack('!H',value[2:4])[0])
					safi = SAFI(ord(value[5]))
					capabilities[k].append((afi,safi))
					continue

				if k == Capabilities.GRACEFUL_RESTART:
					restart = unpack('!H',value[2:4])[0]
					restart_flag = restart >> 12
					restart_time = restart & Graceful.TIME_MASK
					value = value[4:]
					families = []
					while value:
						afi = AFI(unpack('!H',value[:2])[0])
						safi = SAFI(ord(value[2]))
						flag_family = ord(value[0])
						families.append((afi,safi,flag_family))
						value = value[4:]
					capabilities[k] = Graceful(restart_flag,restart_time,families)
					continue

				if k == Capabilities.FOUR_BYTES_ASN:
					capabilities[k] = ASN(unpack('!L',value[2:6])[0]).four()
					continue

				if k == Capabilities.ROUTE_REFRESH:
					capabilities[k] = RouteRefresh()
					continue

				if k == Capabilities.CISCO_ROUTE_REFRESH:
					capabilities[k] = CiscoRouteRefresh()
					continue

				if k not in capabilities:
					capabilities[k] = Unknown(k)
				if value[2:]:
					capabilities[k].append([ord(_) for _ in value[2:]])
			else:
				raise Notify(2,0,'unknow OPEN parameter %s' % hex(key))
	return capabilities

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
	CISCO_ROUTE_REFRESH      = 0x80 # I Can only find reference to this in the router logs
	# 128-255   Reserved for Private Use [RFC5492]

	unassigned = range(70,128)
	reserved = range(128,256)

	def announced (self,capability):
		return self.has_key(capability)

	def __str__ (self):
		r = []
		for key in self.keys():
			if key == self.MULTIPROTOCOL_EXTENSIONS:
				r += ['Multiprotocol for ' + ' '.join(["%s %s" % (str(afi),str(safi)) for (afi,safi) in self[key]])]
			elif key == self.ROUTE_REFRESH:
				r += ['Route Refresh']
			elif key == self.CISCO_ROUTE_REFRESH:
				r += ['Cisco Route Refresh']
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

	def default (self,restarted):
		families = ((AFI(AFI.ipv4),SAFI(SAFI.unicast)),(AFI(AFI.ipv6),SAFI(SAFI.unicast)))

		mp = MultiProtocol()
		mp.extend(families)
		self[Capabilities.MULTIPROTOCOL_EXTENSIONS] = mp 

		# XXX: RFC 4727 Section 4.0, says that the time SHOULD be inferiour or equal to the HOLDTIME ... 
		if restarted:
			self[Capabilities.GRACEFUL_RESTART] = Graceful(Graceful.RESTART_STATE,120,[(afi,safi,Graceful.FORWARDING_STATE) for (afi,safi) in families])
		else:
			self[Capabilities.GRACEFUL_RESTART] = Graceful(0x0,120,[(afi,safi,Graceful.FORWARDING_STATE) for (afi,safi) in families])

		return self

	def pack (self):
		rs = []
		for k,capabilities in self.iteritems():
			for capability in capabilities.extract():
				rs.append("%s%s%s" % (chr(k),chr(len(capability)),capability))
		parameters = "".join(["%s%s%s" % (chr(2),chr(len(r)),r) for r in rs])
		return "%s%s" % (chr(len(parameters)),parameters)

	def __str__ (self):
		r = []
		for k in self.keys():
			r.append(str(self[k]))
		return ', '.join(r)
