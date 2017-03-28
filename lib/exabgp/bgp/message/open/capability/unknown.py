# encoding: utf-8
"""
unknown.py

Created by Thomas Mangin on 2014-06-30.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

from exabgp.bgp.message.open.capability.capability import Capability

# ============================================================ UnknownCapability
#


@Capability.unknown
class UnknownCapability (Capability):
	def set (self, capability, data=b''):
		self.capability = capability
		self.data = data
		return self

	def __str__ (self):
		if self.capability in Capability.CODE.reserved:
			return 'Reserved %s' % str(self.capability)
		if self.capability in Capability.CODE.unassigned:
			return 'Unassigned %s' % str(self.capability)
		return 'Unknown %s' % str(self.capability)

	def json (self):
		if self.capability in Capability.CODE.reserved:
			iana = 'reserved'
		elif self.capability in Capability.CODE.unassigned:
			iana = 'unassigned'
		else:
			iana = 'unknown'
		return '{ "name": "unknown", "iana": "%s", "value": %d, "raw": "%s" }' % (iana,self.capability,self.data)

	def extract (self):
		return []

	@staticmethod
	def unpack_capability (instance, data, capability):
		return instance.set(capability,data)
