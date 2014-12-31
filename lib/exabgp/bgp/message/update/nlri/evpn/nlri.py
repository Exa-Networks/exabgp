"""
evpn.py

Created by Thomas Morin on 2014-06-23.
Copyright (c) 2014-2015 Orange. All rights reserved.
"""

from struct import pack

from exabgp.protocol.family import AFI
from exabgp.protocol.family import SAFI

# ========================================================================= EVPN

# +-----------------------------------+
# |    Route Type (1 octet)           |
# +-----------------------------------+
# |     Length (1 octet)              |
# +-----------------------------------+
# | Route Type specific (variable)    |
# +-----------------------------------+

class EVPN (object):
	registered_evpn = dict()
	# CODE : NEED to be defined in the subclasses
	NAME = 'unknown'
	SHORT_NAME = 'unknown'

	# lower case to match the class Address API
	afi = AFI(AFI.l2vpn)
	safi = SAFI(SAFI.evpn)

	def __init__(self,packed):
		self.packed = packed

	def _prefix (self):
		return "evpn:%s:" % (self._name.get(self.CODE,'unknown').lower())

	def __str__ (self):
		return "evpn:%s:%s" % (self._name.get(self.CODE,'unknown').lower(),'0x' + ''.join('%02x' % ord(_) for _ in self.packed))

	def __repr__(self):
		return str(self)

	def pack(self):
		return pack('!BB',self.CODE,len(self.packed)) + self.packed

	def __len__ (self):
		return len(self.packed) + 2

	# For subtype 2 (MAC/IP advertisement route),
	# we will have to ignore a part of the route, so this method will be overridden

	def __cmp__(self,other):
		if not isinstance(other,EVPN):
			return -1
		if self.CODE != other.CODE:
			return -1
		if self.packed != other.packed:
			return -1
		return 0

	def __hash__(self):
		return hash("%s:%s:%s:%s" % (self.afi,self.safi,self.CODE,self.packed))

	@classmethod
	def register_evpn (cls):
		cls.registered_evpn[cls.CODE] = cls

	@classmethod
	def unpack(cls,data):
		code = ord(data[0])
		length = ord(data[1])

		if code in cls.registered_evpn:
			return cls.registered_evpn[code].unpack(data[length+1:])
		klass = cls(data[length+1:])
		klass.CODE = code
		return klass
