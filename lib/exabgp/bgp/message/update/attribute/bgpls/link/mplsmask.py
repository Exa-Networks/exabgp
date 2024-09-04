# encoding: utf-8
"""
mplsmask.py

Created by Evelio Vila on 2016-12-01.
Copyright (c) 2014-2017 Exa Networks. All rights reserved.
"""
from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.update.attribute.bgpls.linkstate import LINKSTATE, LsGenericFlags

#      0                   1                   2                   3
#      0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
#     +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#     |              Type             |             Length            |
#     +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#     |L|R|  Reserved |
#     +-+-+-+-+-+-+-+-+
#     https://tools.ietf.org/html/rfc7752#section-3.3.2.2  MPLS Protocol Mask
#
#   +------------+------------------------------------------+-----------+
#   |    Bit     | Description                              | Reference |
#   +------------+------------------------------------------+-----------+
#   |    'L'     | Label Distribution Protocol (LDP)        | [RFC5036] |
#   |    'R'     | Extension to RSVP for LSP Tunnels        | [RFC3209] |
#   |            | (RSVP-TE)                                |           |
#   | 'Reserved' | Reserved for future use                  |           |
#   +------------+------------------------------------------+-----------+


@LINKSTATE.register()
class MplsMask(object):
    TLV = 1094

    def __init__(self, mplsflags):
        self.mplsflags = mplsflags

    def __repr__(self):
        return "MPLS Protocol mask: %s" % (self.mplsflags)

    @classmethod
    def unpack(cls, data, length):

        if length > 1:
            raise Notify(3, 5, "LINK TLV length too large")
        else:
            mpls_mask = LsGenericFlags.unpack(data[0:1], LsGenericFlags.LS_MPLS_MASK)
            return cls(mplsflags=mpls_mask)

    def json(self, compact=None):
        return '"mpls-mask": {}'.format(self.mplsflags.json())
