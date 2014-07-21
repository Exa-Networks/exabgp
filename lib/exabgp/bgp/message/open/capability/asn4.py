# encoding: utf-8
"""
asn4.py

Created by Thomas Mangin on 2014-06-30.
Copyright (c) 2009-2013 Exa Networks. All rights reserved.
"""

from exabgp.bgp.message.open.asn import ASN
from exabgp.bgp.message.open.capability import Capability
from exabgp.bgp.message.open.capability.id import CapabilityID

# ========================================================================= ASN4
#

class ASN4 (Capability,ASN):
	ID = CapabilityID.FOUR_BYTES_ASN

	def __init__ (self,value=0):
		ASN.__init__(self,value)

	def __str__ (self):
		return '"ASN4(%d)"' % int(self)

	@staticmethod
	def unpack (what,instance,data):
		# XXX: FIXME: if instance is not ASN(0) we have two ASN - raise
		instance = ASN.unpack(data,ASN4)
		return instance

ASN4.register_capability()
