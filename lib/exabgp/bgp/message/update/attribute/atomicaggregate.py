# encoding: utf-8
"""
atomicaggregate.py

Created by Thomas Mangin on 2012-07-14.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

from exabgp.bgp.message.update.attribute.attribute import Attribute
from exabgp.bgp.message.notification import Notify


# ========================================================== AtomicAggregate (6)
#

class AtomicAggregate (Attribute):
	ID = Attribute.CODE.ATOMIC_AGGREGATE
	FLAG = Attribute.Flag.TRANSITIVE
	CACHING = True

	__slots__ = []

	def pack (self, negotiated=None):
		return self._attribute('')

	def __len__ (self):
		return 0

	def __str__ (self):
		return ''

	def __cmp__ (self, other):
		if not isinstance(other,self.__class__):
			return -1
		return 0

	def __hash__ (self):
		return 0

	@classmethod
	def unpack (cls, data, negotiated):
		if data:
			raise Notify(3,2,'invalid ATOMIC_AGGREGATE %s' % [hex(ord(_)) for _ in data])
		return cls()

	@classmethod
	def setCache (cls):
		# There can only be one, build it now :)
		cls.cache[Attribute.CODE.ATOMIC_AGGREGATE][''] = cls()

AtomicAggregate.setCache()
