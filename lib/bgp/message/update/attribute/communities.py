#!/usr/bin/env python
# encoding: utf-8
"""
community.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009 Exa Networks. All rights reserved.
"""

import socket
from struct import pack,unpack

from bgp.utils import *
from bgp.message.update.attribute.parent import Attribute,Flag

# =================================================================== Community

def to_Community (data):
	separator = data.find(':')
	if separator > 0:
		# XXX: Check that the value do not overflow 16 bits
		return Community((int(data[:separator])<<16) + int(data[separator+1:]))
	elif len(data) >=2 and data[1] in 'xX':
		return Community(long(data,16))
	else:
		return Community(long(data))

class Community (object):
	def __init__ (self,value):
		self.value = value
	
	def pack (self):
		return pack('!L',self.value)

	def __str__ (self):
		return "%d:%d" % (self.value >> 16, self.value & 0xFFFF)

	def __len__ (self):
		return 4

	def __cmp__ (self,other):
		if type(self) == type(other):
			return cmp(self.value,other.value)
		return cmp(self.value,other)

# =================================================================== Communities (8)

def new_Communities (data):
	communities = Communities()
	while data:
		community = unpack('!L',data[:4])
		data = data[4:]
		communities.add(Community(community))
	return communities

class Communities (Attribute):
	ID = Attribute.COMMUNITY
	FLAG = Flag.TRANSITIVE|Flag.OPTIONAL
	MULTIPLE = False

	def __init__ (self,value=None):
		# Must be None as = param is only evaluated once
		if value: v = value
		else: v = []
		Attribute.__init__(self,v)

	def add(self,data):
		return self.value.append(data)

	def pack (self):
		if len(self.value):
			return self._attribute(''.join([c.pack() for c in self.value])) 
		return ''

	# XXX: Check if this is right ........
	def __len__ (self):
		return 2 + len(self.values)*4


	def __str__ (self):
		l = len(self.value)
		if l > 1:
			return "[ %s ]" % " ".join(str(community) for community in self.value)
		if l == 1:
			return str(self.value[0])
		return ""

# =================================================================== ECommunity

def to_ECommunity (data):
	separator = data.find(':')
	if separator > 0:
		# XXX: Check that the value do not overflow 16 bits
		return ECommunity((int(data[:separator])<<16) + int(data[separator+1:]))
	elif len(data) >=2 and data[1] in 'xX':
		return ECommunity(long(data,16))
	else:
		return ECommunity(long(data))


# http://www.iana.org/assignments/bgp-extended-communities

class ECommunity (object):
	# size of value for data (boolean: is extended)
	length_value = {False:7, True:6}
	name = {False: 'regular', True: 'extended'}
	
	def __init__ (self,value):
		# Two top bits are iana and transitive bits
		self.value = value

	def iana (self):
		return not not (self.value[0] & 0x80)

	def transitive (self):
		return not not (self.value[0] & 0x40)

	def pack (self):
		return self.value

	def __str__ (self):
		return '[ ' + ' '.join([hex(ord(c)) for c in self.value]) + ' ]'

	def __len__ (self):
		return 8

	def __cmp__ (self,other):
		return cmp(self.pack(),other.pack())

# =================================================================== ECommunities (16)

def new_ASCommunity (subtype,asn,data,transitive):
	r = chr(0x00)
	if transitive: r += chr(0x40)
	return r + chr(subtype) + pack('!N',asn) + ''.join([chr(c) for c in data[:4]])

def new_IPv4Community (subtype,data,transitive):
	r = chr(0x01)
	if transitive: r += chr(0x40)
	return r + chr(subtype) + socket.inet_pton(socket.AF_INET,ipv4) + ''.join([chr(c) for c in data[:2]])

def new_OpaqueCommunity (subtype,data,transitive):
	r = chr(0x03)
	if transitive: r += chr(0x40)
	return r + chr(subtype) + ''.join([chr(c) for c in data[:6]])

def new_RouteTargetCommunity (asn,number,hightype=0x01):
	# hightype must be 0x01, 0x02 or 0x03
	# 0x00, 0x02 Number is administrated by a global authority
	# 0x01, Number is administered by the ASN owner
	return chr(hightype) + chr(0x02) + pack('!N',asn) + pack('!L',number)

# See RFC4364
def new_RouteOriginCommunity (asn,number,hightype=0x01):
	# hightype must be 0x01, 0x02 or 0x03
	# 0x00, 0x02 Number is administrated by a global authority
	# 0x01, Number is administered by the ASN owner
	return chr(hightype) + chr(0x03) + pack('!N',asn) + pack('!L',number)

def new_ECommunities (data):
	communities = ECommunities()
	while data:
		ECommunity = unpack(data[:8])
		data = data[8:]
		communities.add(ECommunity(ECommunity))
	return communities

class ECommunities (Communities):
	ID = Attribute.EXTENDED_COMMUNITY
