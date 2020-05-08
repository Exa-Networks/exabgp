# encoding: utf-8
"""
igpextags.py

Created by Evelio Vila on 2016-12-01.
Copyright (c) 2014-2017 Exa Networks. All rights reserved.
"""

from struct import unpack

from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.update.attribute.bgpls.linkstate import LINKSTATE

#      0                   1                   2                   3
#      0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
#     +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#     |              Type             |             Length            |
#     +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#     //                Extended Route Tag (one or more)             //
#     +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#     https://tools.ietf.org/html/rfc7752#section-3.3.3.3


@LINKSTATE.register()
class IgpExTags(object):
    TLV = 1154

    def __init__(self, igpextags):
        self.igpextags = igpextags

    def __repr__(self):
        return "IGP Extended Route Tags: %s" % (self.igpextags)

    @classmethod
    def unpack(cls, data, length):
        tags = []
        n = length // 8
        ind = 0
        for i in list(range(n)):
            tag = unpack("!Q", data[ind : 8 * (i + 1)])[0]
            tags.append(tag)
            ind += 8
        return cls(igpextags=tags)

    def json(self, compact=None):
        return '"igp-extended-route-tags": %s' % self.igpextags
