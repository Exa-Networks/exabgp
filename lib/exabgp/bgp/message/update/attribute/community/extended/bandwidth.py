# encoding: utf-8
"""
bandwidth.py

Created by Thomas Mangin on 2017-07-02.
Copyright (c) 2014-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from struct import pack
from struct import unpack

from exabgp.bgp.message.update.attribute.community.extended import ExtendedCommunity

# ==================================================================== Bandwidth
# draft-ietf-idr-link-bandwidth-06


@ExtendedCommunity.register
class Bandwidth(ExtendedCommunity):
    COMMUNITY_TYPE = 0x40
    COMMUNITY_SUBTYPE = 0x04

    __slots__ = ['encaps', 'control', 'mtu', 'reserved']

    def __init__(self, asn, speed, community=None):
        self.asn = asn
        self.speed = speed
        ExtendedCommunity.__init__(self, community if community is not None else pack("!Hf", asn, speed))

    def __repr__(self):
        return "bandwith:%d:%0.f" % (self.asn, self.speed)

    @staticmethod
    def unpack(data):
        asn, speed = unpack('!Hf', data[2:8])
        return Bandwidth(asn, speed, data[:8])
