# encoding: utf-8
"""

Support for draft-heitz-idr-large-community-03

Copyright (c) 2016 Job Snijders <job@ntt.net>
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

from exabgp.bgp.message.update.attribute import Attribute

from struct import pack
from struct import unpack

class LargeCommunity (Attribute):
	MAX = 0xFFFFFFFFFFFFFFFFFFFFFFFF

	cache = {}
	caching = True

	__slots__ = ['large_community','_str']

	def __init__ (self, large_community):
		self.large_community = large_community
		self._str = "%d:%d:%d" % unpack('!LLL', self.large_community)

	def __eq__ (self, other):
		return self.large_community == other.large_community

	def __ne__ (self, other):
		return self.large_community != other.large_community

	def __lt__ (self, other):
		return self.large_community < other.large_community

	def __le__ (self, other):
		return self.large_community <= other.large_community

	def __gt__ (self, other):
		return self.large_community > other.large_community

	def __ge__ (self, other):
		return self.large_community >= other.large_community

	def json (self):
		return "[ %d, %d , %d ]" % unpack('!LLL', self.large_community)

	def pack (self, negotiated=None):
		return self.large_community

	def __repr__ (self):
		return self._str

	def __len__ (self):
		return 12

	@classmethod
	def unpack (cls, large_community, negotiated):
		return cls(large_community)

	@classmethod
	def cached (cls, large_community):
		if cls.caching and large_community in cls.cache:
			return cls.cache[large_community]
		instance = cls(large_community)
		if cls.caching:
			cls.cache[large_community] = instance
		return instance
