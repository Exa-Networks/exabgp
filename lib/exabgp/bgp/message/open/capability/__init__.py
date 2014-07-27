# encoding: utf-8
"""
capability/__init__.py

Created by Thomas Mangin on 2012-07-17.
Copyright (c) 2009-2013 Exa Networks. All rights reserved.
"""

# =================================================================== Capability
#

from exabgp.bgp.message.notification import Notify


class Capability (object):

	class ID (object):
		RESERVED                 = 0x00  # [RFC5492]
		MULTIPROTOCOL_EXTENSIONS = 0x01  # [RFC2858]
		ROUTE_REFRESH            = 0x02  # [RFC2918]
		OUTBOUND_ROUTE_FILTERING = 0x03  # [RFC5291]
		MULTIPLE_ROUTES          = 0x04  # [RFC3107]
		EXTENDED_NEXT_HOP        = 0x05  # [RFC5549]
		#6-63      Unassigned
		GRACEFUL_RESTART         = 0x40  # [RFC4724]
		FOUR_BYTES_ASN           = 0x41  # [RFC4893]
		# 66 Deprecated
		DYNAMIC_CAPABILITY       = 0x43  # [Chen]
		MULTISESSION_BGP_RFC     = 0x44  # [draft-ietf-idr-bgp-multisession]
		ADD_PATH                 = 0x45  # [draft-ietf-idr-add-paths]
		ENHANCED_ROUTE_REFRESH   = 0x46  # [draft-ietf-idr-bgp-enhanced-route-refresh]
		OPERATIONAL              = 0x47  # ExaBGP only ...
		# 70-127    Unassigned
		CISCO_ROUTE_REFRESH      = 0x80  # I Can only find reference to this in the router logs
		# 128-255   Reserved for Private Use [RFC5492]
		MULTISESSION_BGP         = 0x83  # What Cisco really use for Multisession (yes this is a reserved range in prod !)

		EXTENDED_MESSAGE         = -1    # No yet defined by draft http://tools.ietf.org/html/draft-ietf-idr-extended-messages-02.txt

		unassigned = range(70,128)
		reserved = range(128,256)

		# Internal
		AIGP = 0xFF00


	registered_capability = dict()
	_fallback_capability = None

	@staticmethod
	def hex (data):
		return '0x' + ''.join('%02x' % ord(_) for _ in data)

	@classmethod
	def fallback_capability (cls):
		if cls._fallback_capability is not None:
			raise RuntimeError('only one fallback function can be registered')
		cls._fallback_capability = cls

	@classmethod
	def register_capability (cls,capability=None):
		what = cls.ID if capability is None else capability
		if what in cls.registered_capability:
			raise RuntimeError('only one class can be registered per capability')
		cls.registered_capability[what] = cls

	@classmethod
	def klass (cls,what):
		if what in cls.registered_capability:
			kls = cls.registered_capability[what]
			kls.ID = what
			return kls
		if cls._fallback_capability:
			return cls._fallback_capability
		raise Notify (2,4,'can not handle capability %s' % what)

	@classmethod
	def unpack (cls,capability,capabilities,data):
		if capability in capabilities:
			return cls.klass(capability).unpack(capability,capabilities[capability],data)
		return cls.klass(capability).unpack(capability,Capability.klass(capability)(),data)


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

from exabgp.protocol.family import AFI
from exabgp.protocol.family import SAFI
from exabgp.bgp.message.notification import Notify

# Must be imported for the register API to work
from exabgp.bgp.message.open.capability.addpath import AddPath
from exabgp.bgp.message.open.capability.asn4 import ASN4
from exabgp.bgp.message.open.capability.graceful import Graceful
from exabgp.bgp.message.open.capability.mp import MultiProtocol
from exabgp.bgp.message.open.capability.ms import MultiSession
from exabgp.bgp.message.open.capability.operational import Operational
from exabgp.bgp.message.open.capability.refresh import RouteRefresh
from exabgp.bgp.message.open.capability.refresh import EnhancedRouteRefresh
from exabgp.bgp.message.open.capability.unknown import UnknownCapability
# /forced import

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
		self[Capability.ID.MULTIPROTOCOL_EXTENSIONS] = mp

		if neighbor.asn4:
			self[Capability.ID.FOUR_BYTES_ASN] = ASN4(neighbor.local_as)

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
			self[Capability.ID.ADD_PATH] = AddPath(ap_families,neighbor.add_path)

		if graceful:
			if restarted:
				self[Capability.ID.GRACEFUL_RESTART] = Graceful().set(Graceful.RESTART_STATE,graceful,[(afi,safi,Graceful.FORWARDING_STATE) for (afi,safi) in families])
			else:
				self[Capability.ID.GRACEFUL_RESTART] = Graceful().set(0x0,graceful,[(afi,safi,Graceful.FORWARDING_STATE) for (afi,safi) in families])

		if neighbor.route_refresh:
			self[Capability.ID.ROUTE_REFRESH] = RouteRefresh()
			self[Capability.ID.ENHANCED_ROUTE_REFRESH] = EnhancedRouteRefresh()

		# MUST be the last key added
		if neighbor.multisession:
			self[Capability.ID.MULTISESSION_BGP] = MultiSession().set([Capability.ID.MULTIPROTOCOL_EXTENSIONS])
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
				raise Notify(2,0,"Bad length for OPEN %s (<2) %s" % (name,Capability.hex(data)))
			l = ord(data[1])
			boundary = l+2
			if len(data) < boundary:
				raise Notify(2,0,"Bad length for OPEN %s (buffer underrun) %s" % (name,Capability.hex(data)))
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

from exabgp.util.enumeration import Enumeration
REFRESH = Enumeration ('absent','normal','enhanced')
