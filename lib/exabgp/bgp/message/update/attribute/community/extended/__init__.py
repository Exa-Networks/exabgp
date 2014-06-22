# encoding: utf-8
"""
community.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2013 Exa Networks. All rights reserved.
"""

from struct import unpack

from exabgp.bgp.message.update.attribute.id import AttributeID
from exabgp.bgp.message.update.attribute import Flag

# XXX: Should subclasses register with transitivity ?

class ExtendedCommunity (object):
	ID = AttributeID.EXTENDED_COMMUNITY
	FLAG = Flag.TRANSITIVE|Flag.OPTIONAL
	MULTIPLE = False

	_known = {}

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

	def pack (self,asn4=None):
		return self.community

	def json (self):
		return '[ %s, %s, %s, %s, %s, %s, %s, %s ]' % unpack('!BBBBBBBB',self.community)

	def __str__ (self):
		h = 0x00
		for byte in self.community:
			h <<= 8
			h += ord(byte)
		return "0x%016X" % h

	def __len__ (self):
		return 8

	def __hash__ (self):
		return hash(self.community)

	def __cmp__ (self,other):
		if not isinstance(other, ExtendedCommunity):
			return -1
		return cmp(self.community,other.community)

	@staticmethod
	def unpack (data):
		# 30/02/12 Quagga communities for soo and rt are not transitive when 4360 says they must be, hence the & 0x0FFF
		community = (ord(data[0])&0x0F,ord(data[1]))
		if community in ExtendedCommunity._known:
			return ExtendedCommunity._known[community].unpack(data)
		return ExtendedCommunity(data)
