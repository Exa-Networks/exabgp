#!/usr/bin/env python
# encoding: utf-8
"""
capability.py

Created by Thomas Mangin on 2012-07-17.
Copyright (c) 2012 Exa Networks. All rights reserved.
"""

from exabgp.protocol.family import AFI,SAFI
from exabgp.bgp.message.open.capability.id import CapabilityID
from exabgp.bgp.message.open.capability.mp import MultiProtocol
from exabgp.bgp.message.open.capability.graceful import Graceful
from exabgp.bgp.message.open.capability.ms import MultiSession
from exabgp.bgp.message.open.capability.addpath import AddPath

# =================================================================== Unknown

class Unknown (object):
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
	AUTHENTIFICATION_INFORMATION = 0x01 # Depreciated
	CAPABILITIES                 = 0x02

	def __str__ (self):
		if self == 0x01: return "AUTHENTIFICATION INFORMATION"
		if self == 0x02: return "OPTIONAL"
		return 'UNKNOWN'

# =================================================================== Capabilities
# http://www.iana.org/assignments/capability-codes/

class Capabilities (dict):
	def announced (self,capability):
		return self.has_key(capability)

	# XXX: Should we not call the __str__ function of all the created capability classes ?
	def __str__ (self):
		r = []
		for key in self.keys():
			if key == CapabilityID.MULTIPROTOCOL_EXTENSIONS:
				r += [str(self[key])]
			elif key == CapabilityID.ROUTE_REFRESH:
				r += ['Route Refresh']
			elif key == CapabilityID.CISCO_ROUTE_REFRESH:
				r += ['Cisco Route Refresh']
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
			elif key in CapabilityID.reserved:
				r += ['private use capability %d' % key]
			elif key in CapabilityID.unassigned:
				r += ['unassigned capability %d' % key]
			else:
				r += ['unhandled capability %d' % key]
		return ', '.join(r)

	def default (self,neighbor,restarted):
		graceful = neighbor.graceful_restart
		families = neighbor.families()

		mp = MultiProtocol()
		mp.extend(families)
		self[CapabilityID.MULTIPROTOCOL_EXTENSIONS] = mp
		self[CapabilityID.FOUR_BYTES_ASN] = neighbor.local_as

		if neighbor.add_path:
			ap_families = []
			if (AFI(AFI.ipv4),SAFI(SAFI.unicast)) in families:
				ap_families.append((AFI(AFI.ipv4),SAFI(SAFI.unicast)))
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
