# encoding: utf-8
"""
atomicaggregate.py

Created by Thomas Mangin on 2012-07-14.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from exabgp.util import ordinal
from exabgp.bgp.message.update.attribute.attribute import Attribute
from exabgp.bgp.message.notification import Notify


# ========================================================== AtomicAggregate (6)
#


@Attribute.register()
class AtomicAggregate(Attribute):
    ID = Attribute.CODE.ATOMIC_AGGREGATE
    FLAG = Attribute.Flag.TRANSITIVE
    CACHING = True

    __slots__ = []

    # Inherited from Attribute
    # def __eq__ (self, other):
    # def __ne__ (self, other):

    def pack(self, negotiated=None):
        return self._attribute(b'')

    def __len__(self):
        return 0

    def __repr__(self):
        return ''

    def __hash__(self):
        return 0

    @classmethod
    def unpack(cls, data, negotiated):
        if data:
            raise Notify(3, 2, 'invalid ATOMIC_AGGREGATE %s' % [hex(ordinal(_)) for _ in data])
        return cls()

    @classmethod
    def setCache(cls):
        # There can only be one, build it now :)
        cls.cache[Attribute.CODE.ATOMIC_AGGREGATE][''] = cls()


AtomicAggregate.setCache()
