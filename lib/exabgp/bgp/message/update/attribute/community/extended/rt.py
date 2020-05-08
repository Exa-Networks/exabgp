# encoding: utf-8
"""
rt.py

Created by Thomas Mangin on 2014-06-20.
Copyright (c) 2014-2017 Orange. All rights reserved.
Copyright (c) 2014-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from struct import pack
from struct import unpack

from exabgp.protocol.ip import IPv4
from exabgp.bgp.message.open.asn import ASN
from exabgp.bgp.message.update.attribute.community.extended import ExtendedCommunity


# ================================================================== RouteTarget
# RFC 4360 / RFC 7153


class RouteTarget(ExtendedCommunity):
    COMMUNITY_SUBTYPE = 0x02
    LIMIT = 0
    DESCRIPTION = 'target'

    @property
    def la(self):
        return self.community[2 : self.LIMIT]

    @property
    def ga(self):
        return self.community[self.LIMIT : 8]

    def __eq__(self, other):
        return self.COMMUNITY_SUBTYPE == other.COMMUNITY_SUBTYPE and ExtendedCommunity.__eq__(self, other)

    def __ne__(self, other):
        return not self.__eq__(other)


# ============================================================= RouteTargetASN2Number
# RFC 4360 / RFC 7153


@ExtendedCommunity.register
class RouteTargetASN2Number(RouteTarget):
    COMMUNITY_TYPE = 0x00
    LIMIT = 4

    __slots__ = ['asn', 'number']

    def __init__(self, asn, number, transitive=True, community=None):
        self.asn = asn
        self.number = number
        # assert(number < pow(2,32))
        RouteTarget.__init__(self, community if community else pack('!2sHL', self._subtype(transitive), asn, number))

    def __hash__(self):
        return hash((self.asn, self.number))

    def __repr__(self):
        return "%s:%d:%d" % (self.DESCRIPTION, self.asn, self.number)

    @classmethod
    def unpack(cls, data):
        asn, number = unpack('!HL', data[2:8])
        return cls(ASN(asn), number, False, data[:8])


# ============================================================= RouteTargetIPNumber
# RFC 4360 / RFC 7153


@ExtendedCommunity.register
class RouteTargetIPNumber(RouteTarget):
    COMMUNITY_TYPE = 0x01
    LIMIT = 6

    __slots__ = ['ip', 'number']

    def __init__(self, ip, number, transitive=True, community=None):
        self.ip = ip
        self.number = number
        # assert(number < pow(2,16))
        RouteTarget.__init__(
            self, community if community else pack('!2s4sH', self._subtype(transitive), IPv4.pton(ip), number)
        )

    # why could we not simply use ExtendedCommunity.hash ?
    def __hash__(self):
        return hash((self.ip, self.number))

    def __repr__(self):
        return "%s:%s:%d" % (self.DESCRIPTION, self.ip, self.number)

    @classmethod
    def unpack(cls, data):
        ip, number = unpack('!4sH', data[2:8])
        return cls(IPv4.ntop(ip), number, False, data[:8])


# ======================================================== RouteTargetASN4Number
# RFC 4360 / RFC 7153


@ExtendedCommunity.register
class RouteTargetASN4Number(RouteTarget):
    COMMUNITY_TYPE = 0x02
    LIMIT = 6

    __slots__ = ['asn', 'number']

    def __init__(self, asn, number, transitive=True, community=None):
        self.asn = asn
        self.number = number
        # assert(number < pow(2,16))
        RouteTarget.__init__(self, community if community else pack('!2sLH', self._subtype(transitive), asn, number))

    # why could we not simply use ExtendedCommunity.hash ?
    def __hash__(self):
        return hash((self.asn, self.number))

    def __repr__(self):
        return "%s:%dL:%d" % (self.DESCRIPTION, self.asn, self.number)

    @classmethod
    def unpack(cls, data):
        asn, number = unpack('!LH', data[2:8])
        return cls(ASN(asn), number, False, data[:8])
