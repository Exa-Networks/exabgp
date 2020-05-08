# encoding: utf-8
"""
origin.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from exabgp.util import character
from exabgp.util import ordinal
from exabgp.bgp.message.update.attribute.attribute import Attribute


# =================================================================== Origin (1)


@Attribute.register()
class Origin(Attribute):
    ID = Attribute.CODE.ORIGIN
    FLAG = Attribute.Flag.TRANSITIVE
    CACHING = True

    IGP = 0x00
    EGP = 0x01
    INCOMPLETE = 0x02

    __slots__ = ['origin', '_packed']

    def __init__(self, origin, packed=None):
        self.origin = origin
        self._packed = self._attribute(packed if packed else character(origin))

    def __eq__(self, other):
        return self.ID == other.ID and self.FLAG == other.FLAG and self.origin == other.origin

    def __ne__(self, other):
        return not self.__eq__(other)

    def pack(self, negotiated=None):
        return self._packed

    def __len__(self):
        return len(self._packed)

    def __repr__(self):
        if self.origin == 0x00:
            return 'igp'
        if self.origin == 0x01:
            return 'egp'
        if self.origin == 0x02:
            return 'incomplete'
        return 'invalid'

    @classmethod
    def unpack(cls, data, negotiated):
        return cls(ordinal(data), data)

    @classmethod
    def setCache(cls):
        # there can only be three, build them now
        IGP = Origin(Origin.IGP)
        EGP = Origin(Origin.EGP)
        INC = Origin(Origin.INCOMPLETE)

        cls.cache[Attribute.CODE.ORIGIN][IGP.pack()] = IGP
        cls.cache[Attribute.CODE.ORIGIN][EGP.pack()] = EGP
        cls.cache[Attribute.CODE.ORIGIN][INC.pack()] = INC


Origin.setCache()
