# encoding: utf-8
"""
isisarea.py

Created by Evelio Vila on 2016-12-01.
Copyright (c) 2014-2017 Exa Networks. All rights reserved.
"""

from exabgp.vendoring.bitstring import BitArray

from exabgp.bgp.message.notification import Notify

from exabgp.bgp.message.update.attribute.bgpls.linkstate import LINKSTATE

#      0                   1                   2                   3
#      0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
#     +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#     |              Type             |             Length            |
#     +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#     //                 Area Identifier (variable)                  //
#     +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#     https://tools.ietf.org/html/rfc7752#section-3.3.1.2


@LINKSTATE.register()
class IsisArea(object):
    TLV = 1027

    def __init__(self, areaid):
        self.areaid = areaid

    def __repr__(self):
        return "ISIS area id: %s" % (self.areaid)

    @classmethod
    def unpack(cls, data, length):

        b = BitArray(bytes=data)
        return cls(areaid=b.hex)

    def json(self, compact=None):
        return '"area-id": "%s"' % str(self.areaid)
