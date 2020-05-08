# encoding: utf-8
"""
origin.py

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


# ======================================================================= Origin
# RFC 4360 / RFC 7153


class Origin(ExtendedCommunity):
    COMMUNITY_SUBTYPE = 0x03
    LIMIT = 0  # This is to prevent warnings from scrutinizer

    @property
    def la(self):
        return self.community[2 : self.LIMIT]

    @property
    def ga(self):
        return self.community[self.LIMIT : 8]

    def __eq__(self, other):
        return self.COMMUNITY_SUBTYPE == other.COMMUNITY_SUBTYPE and ExtendedCommunity.__eq__(self, other)


# ================================================================== OriginASNIP
# RFC 4360 / RFC 7153


@ExtendedCommunity.register
class OriginASNIP(Origin):
    COMMUNITY_TYPE = 0x00
    LIMIT = 4

    __slots__ = ['asn', 'ip']

    def __init__(self, asn, ip, transitive, community=None):
        self.asn = asn
        self.ip = ip
        Origin.__init__(self, community if community else pack('!2sH4s', self._subtype(), asn, IPv4.pton(ip)))

    def __repr__(self):
        return "origin:%s:%s" % (self.asn, self.ip)

    @staticmethod
    def unpack(data):
        asn, ip = unpack('!H4s', data[2:8])
        return OriginASNIP(ASN(asn), IPv4.ntop(ip), False, data[:8])


# ================================================================== OriginIPASN
# RFC 4360 / RFC 7153


@ExtendedCommunity.register
class OriginIPASN(Origin):
    COMMUNITY_TYPE = 0x01
    LIMIT = 6

    __slots__ = ['asn', 'ip']

    def __init__(self, asn, ip, transitive, community=None):
        self.ip = ip
        self.asn = asn
        Origin.__init__(self, community if community else pack('!2s4sH', self._subtype(), IPv4.pton(ip), asn))

    def __repr__(self):
        return "origin:%s:%s" % (self.ip, self.asn)

    @staticmethod
    def unpack(data):
        ip, asn = unpack('!4sH', data[2:8])
        return OriginIPASN(IPv4.ntop(ip), ASN(asn), False, data[:8])


# ============================================================= OriginASN4Number
# RFC 4360 / RFC 7153


@ExtendedCommunity.register
class OriginASN4Number(Origin):
    COMMUNITY_TYPE = 0x02
    LIMIT = 6

    def __init__(self, asn, number, transitive, community=None):
        self.asn = asn
        self.number = number
        Origin.__init__(self, community if community else pack('!2sLH', self._subtype(), asn, number))

    def __repr__(self):
        return "origin:%sL:%s" % (self.asn, self.number)

    @staticmethod
    def unpack(data):
        asn, number = unpack('!LH', data[2:8])
        return OriginASN4Number(ASN(asn), number, False, data[:8])
