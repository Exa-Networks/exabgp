#!/usr/bin/env python
# encoding: utf-8
"""
labels.py

based on communities.py Created by Thomas Mangin on 2009-11-05.
Modified by Diego Garcia del Rio on 2010-01-05
Copyright (c) 2009 Exa Networks. All rights reserved.
"""

from struct import pack

from bgp.message.update.attribute import AttributeID,Flag,Attribute

# =================================================================== Community

class Label (object):
	def __init__ (self,community):
		self.community = community
	
	def pack (self):
		return pack('!L',self.community)

	def __str__ (self):
		return "%d:%d" % (self.community >> 16, self.community & 0xFFFF)

	def __len__ (self):
		return 4

	def __eq__ (self,other):
		return self.community == other.community

# =================================================================== Communities (8)

class Communities (Attribute):
	ID = AttributeID.COMMUNITY
	FLAG = Flag.TRANSITIVE|Flag.OPTIONAL
	MULTIPLE = False

	def __init__ (self,communities=None):
		# Must be None as = param is only evaluated once
		if communities: 
			self.communities = communities
		else:
			self.communities = []

	def add(self,data):
		return self.communities.append(data)

	def pack (self):
		if len(self.communities):
			return self._attribute(''.join([c.pack() for c in self.communities])) 
		return ''

	def __str__ (self):
		l = len(self.communities)
		if l > 1:
			return "[ %s ]" % " ".join(str(community) for community in self.communities)
		if l == 1:
			return str(self.communities[0])
		return ""

# =================================================================== ECommunity

#def to_ECommunity (data):
#	separator = data.find(':')
#	if separator > 0:
#		# XXX: Check that the value do not overflow 16 bits
#		return ECommunity((int(data[:separator])<<16) + int(data[separator+1:]))
#	elif len(data) >=2 and data[1] in 'xX':
#		return ECommunity(long(data,16))
#	else:
#		return ECommunity(long(data))


# http://www.iana.org/assignments/bgp-extended-communities

class ECommunity (object):
	ID = AttributeID.EXTENDED_COMMUNITY
	FLAG = Flag.TRANSITIVE|Flag.OPTIONAL
	MULTIPLE = False

	# size of value for data (boolean: is extended)
	length_value = {False:7, True:6}
	name = {False: 'regular', True: 'extended'}
	
	def __init__ (self,community):
		# Two top bits are iana and transitive bits
		self.community = community

	def iana (self):
		return not not (self.community[0] & 0x80)

	def transitive (self):
		return not not (self.community[0] & 0x40)

	def pack (self):
		return self.community

	def __str__ (self):
		return '[ ' + ' '.join([hex(ord(c)) for c in self.community]) + ' ]'

	def __len__ (self):
		return 8

	def __cmp__ (self,other):
		return cmp(self.pack(),other.pack())

# =================================================================== ECommunities (16)

#def new_ECommunities (data):
#	communities = ECommunities()
#	while data:
#		ECommunity = unpack(data[:8])
#		data = data[8:]
#		communities.add(ECommunity(ECommunity))
#	return communities

class ECommunities (Communities):
	ID = AttributeID.EXTENDED_COMMUNITY

def _to_FlowCommunity (action,data):
	return ECommunity(pack('!H',action) + data[:6])

# rate is bytes/seconds
def to_FlowTrafficRate (asn,rate):
	return _to_FlowCommunity (0x8006,pack('!H',asn)[:2]+pack('!f',rate))

def to_RouteOriginCommunity (asn,number,hightype=0x01):
	return ECommunity(chr(hightype) + chr(0x03) + pack('!H',asn) + pack('!L',number))

# VRF is ASN:Long
def to_RouteTargetCommunity_00 (asn,number):
	return ECommunity(chr(0x00) + chr(0x02) + pack('!H',asn) + pack('!L',number))

# VRF is A.B.C.D:Short
def to_RouteTargetCommunity_01 (ipn,number):
	return ECommunity(chr(0x01) + chr(0x02) + pack('!L',ipn) + pack('!H',number))

#def to_FlowAction (sample,terminal):
#	bitmask = chr(0)
#	if terminal: bitmask += 0x01
#	if sample: bitmask += 0x02
#	return _to_FlowCommunity (0x8007,chr(0)*5+bitmask)
#
## take a string representing a 6 bytes long hexacedimal number like "0x123456789ABC"
#def to_FlowRedirect (bitmask):
#	route_target = ''
#	for p in range(2,14,2): # 2,4,6,8,10,12
#		route_target += chr(int(bitmask[p:p+2],16))
#	return _to_FlowCommunity (0x8008,route_target)
#
#def to_FlowMark (dscp):
#	return _to_FlowCommunity (0x8009,chr(0)*5 + chr(dscp))
#
#def to_ASCommunity (subtype,asn,data,transitive):
#	r = chr(0x00)
#	if transitive: r += chr(0x40)
#	return ECommunity(r + chr(subtype) + pack('!H',asn) + ''.join([chr(c) for c in data[:4]]))
#
#import socket
#def to_IPv4Community (subtype,data,transitive):
#	r = chr(0x01)
#	if transitive: r += chr(0x40)
#	return ECommunity(r + chr(subtype) + socket.inet_pton(socket.AF_INET,ipv4) + ''.join([chr(c) for c in data[:2]]))
#
#def to_OpaqueCommunity (subtype,data,transitive):
#	r = chr(0x03)
#	if transitive: r += chr(0x40)
#	return ECommunity(r + chr(subtype) + ''.join([chr(c) for c in data[:6]]))

# See RFC4360 
# 0x00, 0x02 Number is administrated by a global authority
# Format is asn:route_target (2 bytes:4 bytes)
# 0x01, Number is administered by the ASN owner
# Format is ip:route_target  (4 bytes:2 bytes)
# 0x02 and 0x03 .. read the RFC :)

