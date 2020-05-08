# encoding: utf-8
"""
igpflags.py

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
#     |D|N|L|P| Resvd.|
#     +-+-+-+-+-+-+-+-+
#     https://tools.ietf.org/html/rfc7752#section-3.3.3.1
#
#           +----------+---------------------------+-----------+
#           |   Bit    | Description               | Reference |
#           +----------+---------------------------+-----------+
#           |   'D'    | IS-IS Up/Down Bit         | [RFC5305] |
#           |   'N'    | OSPF "no unicast" Bit     | [RFC5340] |
#           |   'L'    | OSPF "local address" Bit  | [RFC5340] |
#           |   'P'    | OSPF "propagate NSSA" Bit | [RFC5340] |
#           | Reserved | Reserved for future use.  |           |
#           +----------+---------------------------+-----------+


@LINKSTATE.register()
class IgpFlags(object):
    TLV = 1152

    def __init__(self, igpflags):
        self.igpflags = igpflags

    def __repr__(self):
        return "IGP flags: %s" % (self.igpflags)

    @classmethod
    def unpack(cls, data, length):

        if length > 1:
            raise Notify(3, 5, "IGP Flags TLV length too large")
        else:
            flags = LsGenericFlags.unpack(data[0:1], LsGenericFlags.LS_IGP_FLAGS)
            return cls(igpflags=flags)

    def json(self, compact=None):
        return '"igp-flags": {}'.format(self.igpflags.json())
