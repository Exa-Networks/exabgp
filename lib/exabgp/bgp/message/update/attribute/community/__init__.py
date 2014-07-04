# encoding: utf-8
"""
community.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2013 Exa Networks. All rights reserved.
"""

from exabgp.bgp.message.update.attribute.id import AttributeID
from exabgp.bgp.message.update.attribute import Flag,Attribute

# =================================================================== Communities (8)
# http://www.iana.org/assignments/bgp-extended-communities

class Communities (Attribute):
	ID = AttributeID.COMMUNITY
	FLAG = Flag.TRANSITIVE|Flag.OPTIONAL
	MULTIPLE = False

	__slots__ = ['communities']

	def __init__ (self,communities=None):
		# Must be None as = param is only evaluated once
		if communities:
			self.communities = communities
		else:
			self.communities = []

	def add(self,data):
		return self.communities.append(data)

	def pack (self,asn4=None):
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


class ExtendedCommunities (Communities):
	ID = AttributeID.EXTENDED_COMMUNITY
