# encoding: utf-8
"""
igptags.py

Created by Evelio Vila on 2016-12-01.
Copyright (c) 2014-2017 Exa Networks. All rights reserved.
"""

from struct import unpack

from exabgp.util import split

from exabgp.bgp.message.update.attribute.bgpls.linkstate import LinkState
from exabgp.bgp.message.update.attribute.bgpls.linkstate import BaseLS

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


@LinkState.register()
class IgpTags(BaseLS):
    TLV = 1153
    REPR = 'IGP Route Tags'
    JSON = 'igp-route-tags'
    # XXX: can we find a LEN to check?

    @classmethod
    def unpack(cls, data):
        cls.check(data)
        return cls([unpack('!L', _)[0] for _ in split(data, 4)])
