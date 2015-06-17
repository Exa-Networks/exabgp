# encoding: utf-8
"""
community.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

from struct import pack
from struct import unpack


# ==================================================================== Community
#

class Community (object):
	MAX = 0xFFFFFFFF

	NO_EXPORT            = pack('!L',0xFFFFFF01)
	NO_ADVERTISE         = pack('!L',0xFFFFFF02)
	NO_EXPORT_SUBCONFED  = pack('!L',0xFFFFFF03)
	NO_PEER              = pack('!L',0xFFFFFF04)

	cache = {}
	caching = True

	__slots__ = ['community','_str']

	def __init__ (self, community):
		self.community = community
		if community == self.NO_EXPORT:
			self._str = 'no-export'
		elif community == self.NO_ADVERTISE:
			self._str = 'no-advertise'
		elif community == self.NO_EXPORT_SUBCONFED:
			self._str = 'no-export-subconfed'
		else:
			self._str = "%d:%d" % unpack('!HH',self.community)

	def __eq__ (self, other):
		return self.community == other.community

	def __ne__ (self, other):
		return self.community != other.community

	def __lt__ (self, other):
		return self.community < other.community

	def __le__ (self, other):
		return self.community <= other.community

	def __gt__ (self, other):
		return self.community > other.community

	def __ge__ (self, other):
		return self.community >= other.community

	def json (self):
		return "[ %d, %d ]" % unpack('!HH',self.community)

	def pack (self, negotiated=None):
		return self.community

	def __repr__ (self):
		return self._str

	def __len__ (self):
		return 4

	@classmethod
	def unpack (cls, community, negotiated):
		return cls(community)

	@classmethod
	def cached (cls, community):
		if cls.caching and community in cls.cache:
			return cls.cache[community]
		instance = cls(community)
		if cls.caching:
			cls.cache[community] = instance
		return instance

# Always cache well-known communities, they will be used a lot
if not Community.cache:
	Community.cache[Community.NO_EXPORT] = Community(Community.NO_EXPORT)
	Community.cache[Community.NO_ADVERTISE] = Community(Community.NO_ADVERTISE)
	Community.cache[Community.NO_EXPORT_SUBCONFED] = Community(Community.NO_EXPORT_SUBCONFED)
	Community.cache[Community.NO_PEER] = Community(Community.NO_PEER)
