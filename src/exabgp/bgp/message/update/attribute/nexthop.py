# encoding: utf-8
"""
nexthop.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from exabgp.protocol.family import AFI
from exabgp.protocol.ip import IP
from exabgp.protocol.ip import NoNextHop
from exabgp.bgp.message.update.attribute.attribute import Attribute


# ================================================================== NextHop (3)

# The inheritance order is important and attribute MUST be first for the righ register to be called
# At least until we rename them to be more explicit


@Attribute.register()
class NextHop(Attribute, IP):
    ID = Attribute.CODE.NEXT_HOP
    FLAG = Attribute.Flag.TRANSITIVE
    CACHING = True
    SELF = False

    # XXX: This is a bad API, as it works on non-raw data
    def __init__(self, string, packed=None):
        self.init(string, packed)

    def __eq__(self, other):
        return self.ID == other.ID and self.FLAG == other.FLAG and self._packed == other.ton()

    def __ne__(self, other):
        return not self.__eq__(other)

    def ton(self, negotiated=None, afi=AFI.undefined):
        return self._packed

    def pack(self, negotiated=None):
        return self._attribute(self.ton())

    @classmethod
    def unpack(cls, data, negotiated=None):
        if not data:
            return NoNextHop
        return IP.unpack(data, NextHop)

    def __repr__(self):
        return IP.__repr__(self)


class NextHopSelf(NextHop):
    SELF = True

    def __init__(self, afi):
        self.afi = afi

    def __repr__(self):
        return 'self'

    def ipv4(self):
        return self.afi == AFI.ipv4

    def pack(self, negotiated):
        return self._attribute(negotiated.nexthopself(self.afi).ton())

    def ton(self, negotiated=None, afi=AFI.undefined):
        return negotiated.nexthopself(afi).ton()
