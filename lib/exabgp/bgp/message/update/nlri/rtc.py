# encoding: utf-8
"""
rtc.py

Created by Thomas Morin on 2014-06-10.
Copyright (c) 2014-2017 Orange. All rights reserved.
Copyright (c) 2014-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from struct import pack
from struct import unpack

from exabgp.util import character
from exabgp.util import ordinal
from exabgp.bgp.message.open.asn import ASN
from exabgp.bgp.message.update.attribute import Attribute
from exabgp.bgp.message.update.attribute.community.extended import RouteTarget

from exabgp.protocol.ip import NoNextHop

from exabgp.protocol.family import AFI
from exabgp.protocol.family import SAFI

from exabgp.bgp.message import OUT

from exabgp.bgp.message.update.nlri.nlri import NLRI


@NLRI.register(AFI.ipv4, SAFI.rtc)
class RTC(NLRI):
    # XXX: FIXME: no support yet for RTC variable length with prefixing

    __slots__ = ['origin', 'rt', 'action', 'nexthop']

    def __init__(self, afi, safi, action, origin, rt):
        NLRI.__init__(self, afi, safi)
        self.action = action
        self.origin = origin
        self.rt = rt
        self.nexthop = NoNextHop

    def feedback(self, action):
        if self.nexthop is None and action == OUT.ANNOUNCE:
            return 'rtc nlri next-hop missing'
        return ''

    @classmethod
    def new(cls, afi, safi, origin, rt, nexthop=NoNextHop, action=OUT.UNSET):
        instance = cls(afi, safi, action, origin, rt)
        instance.origin = origin
        instance.rt = rt
        instance.nexthop = nexthop
        instance.action = action
        return instance

    def __len__(self):
        return (4 + len(self.rt)) * 8 if self.rt else 1

    def __str__(self):
        return "rtc %s:%s" % (self.origin, self.rt) if self.rt else "rtc wildcard"

    def __repr__(self):
        return str(self)

    @staticmethod
    def resetFlags(char):
        return character(ordinal(char) & ~(Attribute.Flag.TRANSITIVE | Attribute.Flag.OPTIONAL))

    def pack_nlri(self, negotiated=None):
        # XXX: no support for addpath yet
        # We reset ext com flag bits from the first byte in the packed RT
        # because in an RTC route these flags never appear.
        if self.rt:
            packedRT = self.rt.pack()
            return pack("!BLB", len(self), self.origin, ordinal(RTC.resetFlags(packedRT[0]))) + packedRT[1:]
        return pack("!B", 0)

    @classmethod
    def unpack_nlri(cls, afi, safi, bgp, action, addpath):

        length = ordinal(bgp[0])

        if length == 0:
            return cls(afi, safi, action, ASN(0), None), bgp[1:]

        if length < 8 * 4:
            raise Exception("incorrect RT length: %d (should be >=32,<=96)" % length)

        # We are reseting the flags on the RouteTarget extended
        # community, because they do not make sense for an RTC route

        return (
            cls(
                afi,
                safi,
                action,
                ASN(unpack('!L', bgp[1:5])[0]),
                RouteTarget.unpack(RTC.resetFlags(bgp[5]) + bgp[6:13]),
            ),
            bgp[13:],
        )
