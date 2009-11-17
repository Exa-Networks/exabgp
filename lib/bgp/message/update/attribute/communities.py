#!/usr/bin/env python
# encoding: utf-8
"""
community.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009 Exa Networks. All rights reserved.
"""

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
		Attribute.__init__(self,value if value else [])

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
