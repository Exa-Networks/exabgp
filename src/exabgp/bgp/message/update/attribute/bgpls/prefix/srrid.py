# encoding: utf-8
"""
srrid.py

Created by Evelio Vila
Copyright (c) 2014-2017 Exa Networks. All rights reserved.
"""

from __future__ import annotations

from exabgp.protocol.ip import IP

from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.update.attribute.bgpls.linkstate import LinkState
from exabgp.bgp.message.update.attribute.bgpls.linkstate import BaseLS

#    draft-gredler-idr-bgp-ls-segment-routing-ext-03
#    0                   1                   2                   3
#    0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
#   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#   |            Type               |            Length             |
#   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#   //                  IPv4/IPv6 Address (Router-ID)              //
#   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#     Source Router Identifier (Source Router-ID) TLV


@LinkState.register()
class SrSourceRouterID(BaseLS):
    TLV = 1171
    REPR = 'Source router identifier'
    JSON = 'sr-source-router-id'

    @classmethod
    def unpack(cls, data):
        length = len(data)
        if length not in (4, 16):
            raise Notify(3, 5, 'Error parsing SR Source Router ID. Wrong size')
        return cls(IP.unpack(data))
