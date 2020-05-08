# encoding: utf-8
"""
nodename.py

Created by Evelio Vila on 2016-12-01.
Copyright (c) 2014-2017 Exa Networks. All rights reserved.
"""

from struct import pack
from struct import unpack

from exabgp.bgp.message.notification import Notify

from exabgp.bgp.message.update.attribute.bgpls.linkstate import LINKSTATE

#
#     0                   1                   2                   3
#     0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
#    +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#    |              Type             |             Length            |
#    +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#    //                     Node Name (variable)                    //
#    +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#    https://tools.ietf.org/html/rfc7752#section-3.3.1.5 Opaque Node Attribute Format
#
# 	  This TLV is added here for completeness but we don't look into the TLV.
#   Use of draft-tantsura-bgp-ls-segment-routing-msd-02 in this TLV is not clear


@LINKSTATE.register()
class NodeOpaque(object):
    TLV = 1025

    def __init__(self, opaque):
        self.opaque = opaque

    def __repr__(self):
        return "Node Opaque attribute: %s" % (self.opaque)

    @classmethod
    def unpack(cls, data, length):
        opaque = unpack("!%ds" % length, data[:length])[0]
        return cls(opaque=opaque)
