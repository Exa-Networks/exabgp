# encoding: utf-8
"""
med.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from struct import pack
from struct import unpack

from exabgp.bgp.message.update.attribute.attribute import Attribute


# ====================================================================== MED (4)
#


@Attribute.register()
class MED(Attribute):
    ID = Attribute.CODE.MED
    FLAG = Attribute.Flag.OPTIONAL
    CACHING = True

    __slots__ = ['med', '_packed']

    def __init__(self, med, packed=None):
        self.med = med
        self._packed = self._attribute(packed if packed is not None else pack('!L', med))

    def __eq__(self, other):
        return self.ID == other.ID and self.FLAG == other.FLAG and self.med == other.med

    def __ne__(self, other):
        return not self.__eq__(other)

    def pack(self, negotiated=None):
        return self._packed

    def __len__(self):
        return 4

    def __repr__(self):
        return str(self.med)

    def __hash__(self):
        return hash(self.med)

    @classmethod
    def unpack(cls, data, negotiated):
        return cls(unpack('!L', data)[0])
