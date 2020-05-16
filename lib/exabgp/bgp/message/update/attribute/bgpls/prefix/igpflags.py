# encoding: utf-8
"""
igpflags.py

Created by Evelio Vila on 2016-12-01.
Copyright (c) 2014-2017 Exa Networks. All rights reserved.
"""
from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.update.attribute.bgpls.linkstate import LINKSTATE
from exabgp.bgp.message.update.attribute.bgpls.linkstate import LsGenericFlags

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

# 	RFC 7752 3.3.3.1. IGP Flags TLV


@LINKSTATE.register()
class IgpFlags(LsGenericFlags):
    REPR = 'IGP flags'
    JSON = 'igp-flags'
    TLV = 1152
    FLAGS = ['D', 'N', 'L', 'P', 'RSV', 'RSV', 'RSV', 'RSV']
    LEN = 1
