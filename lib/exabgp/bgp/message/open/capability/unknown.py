# encoding: utf-8
"""
unknown.py

Created by Thomas Mangin on 2014-06-30.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

from exabgp.bgp.message.open.capability import Capability

# ============================================================ UnknownCapability
#

class UnknownCapability (Capability):
	def set (self,value,raw=''):
		self.value = value
		self.raw = raw

	def __str__ (self):
		if self.value in Capability.ID.reserved: return 'Reserved %s' % str(self.value)
		if self.value in Capability.ID.unassigned: return 'Unassigned %s' % str(self.value)
		return 'Unknown %s' % str(self.value)

	def json (self):
		if self.value in Capability.ID.reserved:
			iana = 'reserved'
		elif self.value in Capability.ID.unassigned:
			iana = 'unassigned'
		else:
			iana = 'unknown'
		return '{ "name": "unknown", "iana": "%s", "value": %d, "raw": "%s" }' % (iana,self.value,self.raw)

	def extract (self):
		return []

	@staticmethod
	def unpack (capability,instance,data):
		return instance.set(capability,data)

Capability.fallback_capability(UnknownCapability)
