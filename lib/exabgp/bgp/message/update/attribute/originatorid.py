# encoding: utf-8
"""
originatorid.py

Created by Thomas Mangin on 2012-07-07.
Copyright (c) 2009-2013 Exa Networks. All rights reserved.
"""

import socket

from exabgp.protocol.ip.inet import Inet

from exabgp.bgp.message.update.attribute.id import AttributeID
from exabgp.bgp.message.update.attribute import Flag,Attribute

# =================================================================== OriginatorID (3)

class OriginatorID (Attribute,Inet):
	ID = AttributeID.ORIGINATOR_ID
	FLAG = Flag.OPTIONAL
	MULTIPLE = False

	# Take an IP as value
	def __init__ (self,ip,packed=None):
		if not packed:
			packed = socket.inet_pton(socket.AF_INET,ip)
		Inet.__init__(self,packed)
		# This override Inet.pack too.

	def __cmp__(self,other):
		if not isinstance(other,self.__class__):
			return -1
		if self.packed != other.packed:
			return -1
		return 0

	def pack (self,asn4=None):
		return self._attribute(self.packed)

	def __str__ (self):
		return Inet.__str__(self)

	@staticmethod
	def unpack (data):
		ip = socket.inet_ntop(socket.AF_INET,data[:4])
		return OriginatorID(ip,data)
