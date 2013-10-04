# encoding: utf-8
"""
aigp.py

Created by Thomas Mangin on 2013-09-24.
Copyright (c) 2009-2013 Exa Networks. All rights reserved.
"""

from struct import pack,unpack

from exabgp.bgp.message.update.attribute.id import AttributeID
from exabgp.bgp.message.update.attribute import Flag,Attribute

# =================================================================== AIGP (26)

# 0                   1                   2                   3
# 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
# |     Type      |         Length                |               |
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+               |
# ~                                                               ~
# |                           Value                               |
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+..........................

# Length: Two octets encoding the length in octets of the TLV,
# including the type and length fields.

class TLV (object):
	def __init__(self,type,value):
		self.type = type
		self.value = value


def _TLVFactory (data):
	while data:
		t = ord(data[0])
		l = unpack('!H',data[1:3])[0]
		v,data = data[3:l],data[l:]
		yield TLV(t,v)

def TLVFactory (data):
	return list(_TLVFactory(data))

def pack_tlv (tlvs):
	return ''.join('%s%s%s' % (chr(tlv.type),pack('!H',len(tlv.value)+3),tlv.value) for tlv in tlvs)

class AIGP (Attribute):
	ID = AttributeID.AIGP
	FLAG = Flag.OPTIONAL
	MULTIPLE = False
	TYPES = [1,]

	def __init__ (self,value):
		self.aigp = unpack('!Q',TLVFactory(value)[0].value)[0]
		self.packed = self._attribute(value)

	def pack (self,asn4=None):
		return self.packed

	def __str__ (self):
		return str(self.aigp)
