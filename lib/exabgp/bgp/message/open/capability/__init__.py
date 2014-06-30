# encoding: utf-8
"""
capability/__init__.py

Created by Thomas Mangin on 2012-07-17.
Copyright (c) 2009-2013 Exa Networks. All rights reserved.
"""

from exabgp.protocol.family import AFI,SAFI
from exabgp.bgp.message.open.capability.capability import Capability
from exabgp.bgp.message.open.capability.id import CapabilityID
from exabgp.bgp.message.notification import Notify

# Must be imported for the register API to work
from exabgp.bgp.message.open.capability.addpath import AddPath
from exabgp.bgp.message.open.capability.asn4 import ASN4
from exabgp.bgp.message.open.capability.graceful import Graceful
from exabgp.bgp.message.open.capability.mp import MultiProtocol
from exabgp.bgp.message.open.capability.ms import MultiSession
from exabgp.bgp.message.open.capability.operational import Operational
from exabgp.bgp.message.open.capability.refresh import RouteRefresh,EnhancedRouteRefresh
from exabgp.bgp.message.open.capability.unknown import UnknownCapability
# /forced import

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

	def __str__ (self):
		r = []
		for key in sorted(self.keys()):
			r.append(str(self[key]))
		return ', '.join(r)

	def new (self,neighbor,restarted):
		graceful = neighbor.graceful_restart
		families = neighbor.families()

		mp = MultiProtocol()
		mp.extend(families)
		self[CapabilityID.MULTIPROTOCOL_EXTENSIONS] = mp

		if neighbor.asn4:
			self[CapabilityID.FOUR_BYTES_ASN] = ASN4(neighbor.local_as)

		if neighbor.add_path:
			ap_families = []
			if (AFI(AFI.ipv4),SAFI(SAFI.unicast)) in families:
				ap_families.append((AFI(AFI.ipv4),SAFI(SAFI.unicast)))
			if (AFI(AFI.ipv6),SAFI(SAFI.unicast)) in families:
				ap_families.append((AFI(AFI.ipv6),SAFI(SAFI.unicast)))
			# if (AFI(AFI.ipv4),SAFI(SAFI.nlri_mpls)) in families:
			# 	ap_families.append((AFI(AFI.ipv4),SAFI(SAFI.nlri_mpls)))
			#if (AFI(AFI.ipv6),SAFI(SAFI.unicast)) in families:
			#	ap_families.append((AFI(AFI.ipv6),SAFI(SAFI.unicast)))
			self[CapabilityID.ADD_PATH] = AddPath(ap_families,neighbor.add_path)

		if graceful:
			if restarted:
				self[CapabilityID.GRACEFUL_RESTART] = Graceful().set(Graceful.RESTART_STATE,graceful,[(afi,safi,Graceful.FORWARDING_STATE) for (afi,safi) in families])
			else:
				self[CapabilityID.GRACEFUL_RESTART] = Graceful().set(0x0,graceful,[(afi,safi,Graceful.FORWARDING_STATE) for (afi,safi) in families])

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

	@staticmethod
	def unpack (data):
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

		capabilities = Capabilities()

		option_len = ord(data[0])
		# XXX: FIXME: check the length of data
		if option_len:
			data = data[1:]
			while data:
				key,value,data = _key_values('parameter',data)
				# Paramaters must only be sent once.
				if key == Parameter.AUTHENTIFICATION_INFORMATION:
					raise Notify(2,5)

				if key == Parameter.CAPABILITIES:
					while value:
						capability,capv,value = _key_values('capability',value)
						capabilities[capability] = Capability.unpack(capability,capabilities,capv)
				else:
					raise Notify(2,0,'Unknow OPEN parameter %s' % hex(key))
		return capabilities
