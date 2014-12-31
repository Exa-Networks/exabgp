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
	NO_EXPORT            = pack('!L',0xFFFFFF01)
	NO_ADVERTISE         = pack('!L',0xFFFFFF02)
	NO_EXPORT_SUBCONFED  = pack('!L',0xFFFFFF03)
	NO_PEER              = pack('!L',0xFFFFFF04)

	cache = {}
	caching = True

	__slots__ = ['community','_str']

	def __init__ (self,community):
		self.community = community
		if community == self.NO_EXPORT:
			self._str = 'no-export'
		elif community == self.NO_ADVERTISE:
			self._str = 'no-advertise'
		elif community == self.NO_EXPORT_SUBCONFED:
			self._str = 'no-export-subconfed'
		else:
			self._str = "%d:%d" % unpack('!HH',self.community)

	def __cmp__ (self,other):
		if not isinstance(other,self.__class__):
			return -1
		if self.community != other.community:
			return -1
		return 0

	def json (self):
		return "[ %d, %d ]" % unpack('!HH',self.community)

	def pack (self,negotiated=None):
		return self.community

	def __str__ (self):
		return self._str

	def __len__ (self):
		return 4

	def __eq__ (self,other):
		return self.community == other.community

	def __ne__ (self,other):
		return self.community != other.community

	@classmethod
	def unpack (cls,community,negotiated):
		return cls(community)

	@classmethod
	def cached (cls,community):
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


# ============================================================== Communities (8)
# http://www.iana.org/assignments/bgp-extended-communities

from exabgp.bgp.message.update.attribute.attribute import Attribute
from exabgp.bgp.message.update.attribute.community import Community
from exabgp.bgp.message.update.attribute.community.extended import ExtendedCommunity
from exabgp.bgp.message.notification import Notify

# Unused but required for the registration of the classes
from exabgp.bgp.message.update.attribute.community.extended.encapsulation import Encapsulation
from exabgp.bgp.message.update.attribute.community.extended.l2info import L2Info
from exabgp.bgp.message.update.attribute.community.extended.origin import Origin
from exabgp.bgp.message.update.attribute.community.extended.rt import RouteTarget
from exabgp.bgp.message.update.attribute.community.extended.traffic import TrafficRate
# /required


class Communities (Attribute):
	ID = Attribute.ID.COMMUNITY
	FLAG = Attribute.Flag.TRANSITIVE|Attribute.Flag.OPTIONAL
	MULTIPLE = False

#	__slots__ = ['communities']

	def __init__ (self,communities=None):
		# Must be None as = param is only evaluated once
		if communities:
			self.communities = communities
		else:
			self.communities = []

	def add(self,data):
		return self.communities.append(data)

	def pack (self,negotiated=None):
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

	def json (self):
		return "[ %s ]" % ", ".join(community.json() for community in self.communities)

	@staticmethod
	def unpack (data,negotiated):
		communities = Communities()
		while data:
			if data and len(data) < 4:
				raise Notify(3,1,'could not decode community %s' % str([hex(ord(_)) for _ in data]))
			communities.add(Community.unpack(data[:4],negotiated))
			data = data[4:]
		return communities

Communities.register_attribute()


# ===================================================== ExtendedCommunities (16)
#

class ExtendedCommunities (Communities):
	ID = Attribute.ID.EXTENDED_COMMUNITY

	@staticmethod
	def unpack (data,negotiated):
		communities = ExtendedCommunities()
		while data:
			if data and len(data) < 8:
				raise Notify(3,1,'could not decode extended community %s' % str([hex(ord(_)) for _ in data]))
			communities.add(ExtendedCommunity.unpack(data[:8],negotiated))
			data = data[8:]
		return communities

ExtendedCommunities.register_attribute()
