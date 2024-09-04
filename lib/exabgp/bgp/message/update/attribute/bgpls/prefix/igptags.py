# encoding: utf-8
"""
igptags.py

Created by Evelio Vila on 2016-12-01.
Copyright (c) 2014-2017 Exa Networks. All rights reserved.
"""

from struct import unpack

from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.update.attribute.bgpls.linkstate import LINKSTATE

#   The IGP Route Tag TLV carries original IGP Tags (IS-IS [RFC5130] or
#   OSPF) of the prefix and is encoded as follows:
#
#      0                   1                   2                   3
#      0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
#     +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#     |              Type             |             Length            |
#     +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#     //                    Route Tags (one or more)                 //
#     +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#     https://tools.ietf.org/html/rfc7752#section-3.3.3.2


@LINKSTATE.register()
class IgpTags(object):
    TLV = 1153

    def __init__(self, igptags):
        self.igptags = igptags

    def __repr__(self):
        return "IGP Route Tags: %s" % (self.igptags)

    @classmethod
    def unpack(cls, data, length):
        tags = []
        n = length // 4
        ind = 0
        for i in list(range(n)):
            tag = unpack("!L", data[ind : 4 * (i + 1)])[0]
            tags.append(tag)
            ind += 4
        return cls(igptags=tags)

    def json(self, compact=None):
        return '"igp-route-tags": %s' % self.igptags
