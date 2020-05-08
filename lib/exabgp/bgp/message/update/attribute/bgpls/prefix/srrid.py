# encoding: utf-8
"""
srrid.py

Created by Evelio Vila
Copyright (c) 2014-2017 Exa Networks. All rights reserved.
"""

from exabgp.protocol.ip import IP
from exabgp.bgp.message.update.attribute.bgpls.linkstate import LINKSTATE

#    draft-gredler-idr-bgp-ls-segment-routing-ext-03
#    0                   1                   2                   3
#    0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
#   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#   |            Type               |            Length             |
#   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#   //                  IPv4/IPv6 Address (Router-ID)              //
#   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#     Source Router Identifier (Source Router-ID) TLV


@LINKSTATE.register()
class SrSourceRouterID(object):
    TLV = 1171

    def __init__(self, srid):
        self.srid = srid

    def __repr__(self):
        return "Source router identifier: %s" % (self.srid)

    @classmethod
    def unpack(cls, data, length):
        if len(data) == 4:
            srid = IP.unpack(data[:4])
        elif len(data) == 16:
            srid = IP.unpack(data[:16])
        return cls(srid=srid)

    def json(self, compact=None):
        return '"sr-source-router-id": "%s"' % str(self.srid)
