# encoding: utf-8
"""
nexthop.py

Created by Thomas Mangin on 2019-05-23.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from struct import pack
from exabgp.protocol.family import AFI
from exabgp.protocol.family import SAFI

from exabgp.bgp.message.open.capability.capability import Capability

# ================================================================ NextHop
#


@Capability.register()
class NextHop(Capability, list):
    ID = Capability.CODE.NEXTHOP

    def __init__(self, data=[]):
        for afi, safi, nhafi in data:
            self.add_nexthop(afi, safi, nhafi)

    def add_nexthop(self, afi, safi, nhafi):
        if (afi, safi, nhafi) not in self:
            self.append((afi, safi, nhafi))

    def __str__(self):
        return (
            'NextHop(' + ','.join(["%s %s %s" % (str(afi), str(safi), str(nhafi)) for (afi, safi, nhafi) in self]) + ')'
        )

    def json(self):
        return '{ "name": "nexthop", "conversion": [%s ] }' % ','.join(
            [' "%s/%s/%s"' % (str(afi), str(safi), str(nhafi)) for (afi, safi, nhafi) in self]
        )

    def extract(self):
        rs = b''
        for afi, safi, nhafi in self:
            rs += afi.pack() + pack("!B", 0) + safi.pack() + nhafi.pack()
        return [
            rs,
        ]

    @staticmethod
    def unpack_capability(instance, data, capability=None):  # pylint: disable=W0613
        # XXX: FIXME: we should complain if we have twice the same AFI/SAFI
        # XXX: FIXME: should check that we have not yet seen the capability
        while data:
            afi = AFI.unpack(data[:2])
            safi = SAFI.unpack(data[3])
            nexthop = AFI.unpack(data[4:6])
            instance.add_nexthop(afi, safi, nexthop)
            data = data[6:]
        return instance
