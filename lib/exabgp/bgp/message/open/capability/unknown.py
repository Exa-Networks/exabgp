# encoding: utf-8
"""
unknown.py

Created by Thomas Mangin on 2014-06-30.
Copyright (c) 2009-2013 Exa Networks. All rights reserved.
"""

from exabgp.bgp.message.open.capability import Capability
from exabgp.bgp.message.open.capability.id import CapabilityID


# ============================================================ UnknownCapability
#

class UnknownCapability (Capability):
	def set (self,value,raw=''):
		self.value = value
		self.raw = raw

	def __str__ (self):
		if self.value in CapabilityID.reserved: return 'Reserved %s' % str(self.value)
		if self.value in CapabilityID.unassigned: return 'Unassigned %s' % str(self.value)
		return 'Unknown %s' % str(self.value)

	def extract (self):
		return []

	@staticmethod
	def unpack (capability,instance,data):
		return instance.set(capability,data)

UnknownCapability.fallback_capability()
