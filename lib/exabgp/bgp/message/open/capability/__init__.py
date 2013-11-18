# encoding: utf-8
"""
capability/__init__.py

Created by Thomas Mangin on 2012-07-17.
Copyright (c) 2009-2013 Exa Networks. All rights reserved.
"""

from struct import unpack

from exabgp.protocol.family import AFI,SAFI
from exabgp.bgp.message.open.asn import ASN
from exabgp.bgp.message.open.capability.id import CapabilityID
from exabgp.bgp.message.open.capability.mp import MultiProtocol
from exabgp.bgp.message.open.capability.refresh import RouteRefresh,EnhancedRouteRefresh
from exabgp.bgp.message.open.capability.graceful import Graceful
from exabgp.bgp.message.open.capability.ms import MultiSession
from exabgp.bgp.message.open.capability.addpath import AddPath
from exabgp.bgp.message.open.capability.operational import Operational
from exabgp.bgp.message.notification import Notify

def hexa (value):
	return "%s" % [(hex(ord(_))) for _ in value]

# =================================================================== Unknown

class UnknownCapability (object):
	def __init__ (self,value,raw=''):
		self.value = value
		self.raw = raw

	def __str__ (self):
		if self.value in CapabilityID.reserved: return 'Reserved %s' % str(self.value)
		if self.value in CapabilityID.unassigned: return 'Unassigned %s' % str(self.value)
		return 'unknown %s %s' % (str(self.value),str(self.raw))

	def extract (self):
		return []

# =================================================================== Parameter

class Parameter (int):
	AUTHENTIFICATION_INFORMATION = 0x01  # Depreciated
	CAPABILITIES                 = 0x02

	def __str__ (self):
		if self == 0x01: return "AUTHENTIFICATION INFORMATION"
		if self == 0x02: return "OPTIONAL"
		return 'UNKNOWN'

# =================================================================== Capabilities
# http://www.iana.org/assignments/capability-codes/

# +------------------------------+
# | Capability Code (1 octet)    |
# +------------------------------+
# | Capability Length (1 octet)  |
# +------------------------------+
# | Capability Value (variable)  |
# +------------------------------+

class Capabilities (dict):
	def announced (self,capability):
		return capability in self

	# XXX: Should we not call the __str__ function of all the created capability classes ?
	def __str__ (self):
		r = []
		for key in self.keys():
			if key == CapabilityID.MULTIPROTOCOL_EXTENSIONS:
				r += [str(self[key])]
			elif key == CapabilityID.ROUTE_REFRESH:
				r += [str(self[key])]
			elif key == CapabilityID.CISCO_ROUTE_REFRESH:
				r += ['Cisco Route Refresh']
			elif key == CapabilityID.ENHANCED_ROUTE_REFRESH:
				r += ['Enhanced Route Refresh']
			elif key == CapabilityID.GRACEFUL_RESTART:
				r += ['Graceful Restart']
			elif key == CapabilityID.FOUR_BYTES_ASN:
				r += ['4Bytes AS %d' % self[key]]
			elif key == CapabilityID.MULTISESSION_BGP:
				r += [str(self[key])]
			elif key == CapabilityID.MULTISESSION_BGP_RFC:
				r += ['Multi Session']
			elif key == CapabilityID.ADD_PATH:
				r += [str(self[key])]
			elif key == CapabilityID.OPERATIONAL:
				r += ['Operational']
			elif key in CapabilityID.reserved:
				r += ['private use capability %d' % key]
			elif key in CapabilityID.unassigned:
				r += ['unassigned capability %d' % key]
			else:
				r += ['unhandled capability %d' % key]
		return ', '.join(r)

	def new (self,neighbor,restarted):
		graceful = neighbor.graceful_restart
		families = neighbor.families()

		mp = MultiProtocol()
		mp.extend(families)
		self[CapabilityID.MULTIPROTOCOL_EXTENSIONS] = mp

		if neighbor.asn4:
			self[CapabilityID.FOUR_BYTES_ASN] = neighbor.local_as

		if neighbor.add_path:
			ap_families = []
			if (AFI(AFI.ipv4),SAFI(SAFI.unicast)) in families:
				ap_families.append((AFI(AFI.ipv4),SAFI(SAFI.unicast)))
			if (AFI(AFI.ipv6),SAFI(SAFI.unicast)) in families:
				ap_families.append((AFI(AFI.ipv6),SAFI(SAFI.unicast)))
			if (AFI(AFI.ipv4),SAFI(SAFI.nlri_mpls)) in families:
				ap_families.append((AFI(AFI.ipv4),SAFI(SAFI.nlri_mpls)))
			#if (AFI(AFI.ipv6),SAFI(SAFI.unicast)) in families:
			#	ap_families.append((AFI(AFI.ipv6),SAFI(SAFI.unicast)))
			self[CapabilityID.ADD_PATH] = AddPath(ap_families,neighbor.add_path)

		if graceful:
			if restarted:
				self[CapabilityID.GRACEFUL_RESTART] = Graceful(Graceful.RESTART_STATE,graceful,[(afi,safi,Graceful.FORWARDING_STATE) for (afi,safi) in families])
			else:
				self[CapabilityID.GRACEFUL_RESTART] = Graceful(0x0,graceful,[(afi,safi,Graceful.FORWARDING_STATE) for (afi,safi) in families])

		if neighbor.route_refresh:
			self[CapabilityID.ROUTE_REFRESH] = RouteRefresh()
			self[CapabilityID.ENHANCED_ROUTE_REFRESH] = EnhancedRouteRefresh()

		# MUST be the last key added
		if neighbor.multisession:
			self[CapabilityID.MULTISESSION_BGP] = MultiSession([CapabilityID.MULTIPROTOCOL_EXTENSIONS])
		return self

	def pack (self):
		rs = []
		for k,capabilities in self.iteritems():
			for capability in capabilities.extract():
				rs.append("%s%s%s" % (chr(k),chr(len(capability)),capability))
		parameters = "".join(["%s%s%s" % (chr(2),chr(len(r)),r) for r in rs])
		return "%s%s" % (chr(len(parameters)),parameters)



def _key_values (name,data):
	if len(data) < 2:
		raise Notify(2,0,"Bad length for OPEN %s (<2) %s" % (name,hexa(data)))
	l = ord(data[1])
	boundary = l+2
	if len(data) < boundary:
		raise Notify(2,0,"Bad length for OPEN %s (buffer underrun) %s" % (name,hexa(data)))
	key = ord(data[0])
	value = data[2:boundary]
	rest = data[boundary:]
	return key,value,rest

def CapabilitiesFactory (data):
	capabilities = Capabilities()

	option_len = ord(data[0])
	if option_len:
		data = data[1:]
		while data:
			key,value,data = _key_values('parameter',data)
			# Paramaters must only be sent once.
			if key == Parameter.AUTHENTIFICATION_INFORMATION:
				raise Notify(2,5)

			if key == Parameter.CAPABILITIES:
				while value:
					k,capv,value = _key_values('capability',value)
					# Multiple Capabilities can be present in a single attribute
					#if r:
					#	raise Notify(2,0,"Bad length for OPEN %s (size mismatch) %s" % ('capability',hexa(value)))

					if k == CapabilityID.MULTIPROTOCOL_EXTENSIONS:
						if k not in capabilities:
							capabilities[k] = MultiProtocol()
						afi = AFI(unpack('!H',capv[:2])[0])
						safi = SAFI(ord(capv[3]))
						capabilities[k].append((afi,safi))
						continue

					if k == CapabilityID.GRACEFUL_RESTART:
						restart = unpack('!H',capv[:2])[0]
						restart_flag = restart >> 12
						restart_time = restart & Graceful.TIME_MASK
						value_gr = capv[2:]
						families = []
						while value_gr:
							afi = AFI(unpack('!H',value_gr[:2])[0])
							safi = SAFI(ord(value_gr[2]))
							flag_family = ord(value_gr[0])
							families.append((afi,safi,flag_family))
							value_gr = value_gr[4:]
						capabilities[k] = Graceful(restart_flag,restart_time,families)
						continue

					if k == CapabilityID.FOUR_BYTES_ASN:
						capabilities[k] = ASN(unpack('!L',capv[:4])[0])
						continue

					if k == CapabilityID.CISCO_ROUTE_REFRESH:
						capabilities[k] = RouteRefresh()
						continue

					if k == CapabilityID.ROUTE_REFRESH:
						capabilities[k] = RouteRefresh()
						continue

					if k == CapabilityID.ENHANCED_ROUTE_REFRESH:
						capabilities[k] = EnhancedRouteRefresh()
						continue

					if k == CapabilityID.MULTISESSION_BGP:
						capabilities[k] = MultiSession()
						continue

					if k == CapabilityID.MULTISESSION_BGP_RFC:
						capabilities[k] = MultiSession()
						continue

					if k == CapabilityID.ADD_PATH:
						if k not in capabilities:
							capabilities[k] = AddPath()
						value_ad = capv
						while value_ad:
							afi = AFI(unpack('!H',value_ad[:2])[0])
							safi = SAFI(ord(value_ad[2]))
							sr = ord(value_ad[3])
							capabilities[k].add_path(afi,safi,sr)
							value_ad = value_ad[4:]

					if k == CapabilityID.OPERATIONAL:
						capabilities[k] = Operational()
						continue

					if k not in capabilities:
						capabilities[k] = UnknownCapability(k,[ord(_) for _ in capv])
			else:
				raise Notify(2,0,'Unknow OPEN parameter %s' % hex(key))
	return capabilities
