"""
evpn.py

Created by Thomas Morin on 2014-06-23.
Copyright (c) 2014-2015 Orange. All rights reserved.
"""

from struct import pack

from exabgp.protocol.ip import IP, NoNextHop
from exabgp.protocol.ip.address import Address

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

class EVPN (Address):
	registered_evpn = dict()

	# NEED to be defined in the subclasses
	CODE = -1
	NAME = 'unknown'
	SHORT_NAME = 'unknown'

	# lower case to match the class Address API
	afi = AFI(AFI.l2vpn)
	safi = SAFI(SAFI.evpn)

	def __init__ (self, packed, nexthop, action, path=None):
		Address.__init__(self, EVPN.afi, EVPN.safi)
		self.nexthop = IP.unpack(nexthop) if nexthop else NoNextHop
		self.action = action
		self.packed = packed

	def _prefix (self):
		return "evpn:%s:" % (self.registered_evpn.get(self.CODE,self).SHORT_NAME.lower())

	def __str__ (self):
		return "evpn:%s:%s" % (self.registered_evpn.get(self.CODE,self).SHORT_NAME.lower(),'0x' + ''.join('%02x' % ord(_) for _ in self.packed))

	def __repr__ (self):
		return str(self)

	def pack (self, addpath=None):
		# XXXXXX: addpath not supported yet
		return pack('!BB',self.CODE,len(self.packed)) + self.packed

	def __len__ (self):
		return len(self.packed) + 2

	# For subtype 2 (MAC/IP advertisement route),
	# we will have to ignore a part of the route, so this method will be overridden

	def __cmp__ (self, other):
		if not isinstance(other,EVPN):
			return -1
		if self.CODE != other.CODE:
			return -1
		if self.packed != other.packed:
			return -1
		return 0

	def __eq__(self,other):
		return cmp(self,other)==0

	def __neq__(self,other):
		return cmp(self,other)!=0

	def __hash__ (self):
		return hash("%s:%s:%s:%s" % (self.afi,self.safi,self.CODE,self.packed))

	@staticmethod
	def register_evpn (klass):
		EVPN.registered_evpn[klass.CODE] = klass

	@classmethod
	def unpack (cls, afi, safi, data, addpath, nexthop, action):
		code = ord(data[0])
		length = ord(data[1])

		if code in cls.registered_evpn:
			klass = cls.registered_evpn[code].unpack(data[2:length+2])
		else:
			klass = cls(data[2:length+2], nexthop, action, addpath)
		klass.CODE = code
		klass.action = action
		klass.nexthop = IP.unpack(nexthop) if nexthop else NoNextHop
		klass.addpath = addpath

		return length+2,klass
