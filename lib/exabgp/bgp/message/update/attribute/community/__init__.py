# encoding: utf-8
"""
community.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2013 Exa Networks. All rights reserved.
"""

from exabgp.bgp.message.update.attribute.attribute import Attribute
from exabgp.bgp.message.update.attribute.community.community import Community
from exabgp.bgp.message.update.attribute.community.extended import ExtendedCommunity
from exabgp.bgp.message.notification import Notify

# Unused but required for the registration of the classes
from exabgp.bgp.message.update.attribute.community.extended.encapsulation import Encapsulation
from exabgp.bgp.message.update.attribute.community.extended.l2info import L2Info
from exabgp.bgp.message.update.attribute.community.extended.origin import Origin
from exabgp.bgp.message.update.attribute.community.extended.rt import RouteTarget
from exabgp.bgp.message.update.attribute.community.extended.traffic import TrafficRate
# /required

# ============================================================== Communities (8)
# http://www.iana.org/assignments/bgp-extended-communities

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
