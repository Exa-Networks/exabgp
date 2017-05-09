# encoding: utf-8
"""
community.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

from exabgp.util import ordinal
from exabgp.bgp.message.update.attribute import Attribute

from struct import pack

# ======================================================= ExtendedCommunity (16)
# XXX: Should subclasses register with transitivity ?


class ExtendedCommunity (Attribute):
	ID = Attribute.CODE.EXTENDED_COMMUNITY
	FLAG = Attribute.Flag.TRANSITIVE | Attribute.Flag.OPTIONAL

	COMMUNITY_TYPE    = 0x00  # MUST be redefined by subclasses
	COMMUNITY_SUBTYPE = 0x00  # MUST be redefined by subclasses
	NON_TRANSITIVE    = 0x40

	registered_extended = {}

	@classmethod
	def register (cls, klass):
		cls.registered_extended[(klass.COMMUNITY_TYPE & 0x0F,klass.COMMUNITY_SUBTYPE)] = klass
		return klass

	# size of value for data (boolean: is extended)
	length_value = {False:7, True:6}
	name = {False: 'regular', True: 'extended'}

	__slots__ = ['community']

	def __init__ (self, community):
		# Two top bits are iana and transitive bits
		self.community = community

	def __eq__(self, other):
		return \
			self.ID == other.ID and \
			self.FLAG == other.FLAG and \
			self.community == other.community

	def __ne__(self, other):
		return not self.__eq__(other)

	def __lt__ (self, other):
		return self.community < other.community

	def __le__ (self, other):
		return self.community <= other.community

	def __gt__ (self, other):
		return self.community > other.community

	def __ge__ (self, other):
		return self.community >= other.community

	def iana (self):
		return not not (self.community[0] & 0x80)

	def transitive (self):
		# bit set means "not transitive"
		# RFC4360:
		#   T - Transitive bit
		#     Value 0: The community is transitive across ASes
		#     Value 1: The community is non-transitive across ASes
		return not (self.community[0] & 0x40)

	def pack (self, negotiated=None):
		return self.community

	def _subtype (self, transitive=True):
		# if not transitive -> set the 'transitive' bit, as per RFC4360
		return pack(
			'!BB',
			self.COMMUNITY_TYPE if transitive else self.COMMUNITY_TYPE | self.NON_TRANSITIVE,
			self.COMMUNITY_SUBTYPE
		)

	def json (self):
		h = 0x00
		for byte in self.community:
			h <<= 8
			h += ordinal(byte)
		return "%ld" % h

	def __repr__ (self):
		h = 0x00
		for byte in self.community:
			h <<= 8
			h += ordinal(byte)
		return "0x%016X" % h

	def __len__ (self):
		return 8

	def __hash__ (self):
		return hash(self.community)

	@staticmethod
	def unpack (data, negotiated=None):
		# 30/02/12 Quagga communities for soo and rt are not transitive when 4360 says they must be, hence the & 0x0FFF
		community = (ordinal(data[0]) & 0x0F,ordinal(data[1]))
		if community in ExtendedCommunity.registered_extended:
			return ExtendedCommunity.registered_extended[community].unpack(data)
		return ExtendedCommunity(data)
