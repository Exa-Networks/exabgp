
"""
mplsmask.py

Created by Evelio Vila on 2016-12-01.
Copyright (c) 2014-2017 Exa Networks. All rights reserved.
"""

from __future__ import annotations

from exabgp.bgp.message.update.attribute.bgpls.linkstate import LinkState
from exabgp.bgp.message.update.attribute.bgpls.linkstate import FlagLS

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

# 	RFC 7752 3.3.2.2.  MPLS Protocol Mask TLV


@LinkState.register()
class MplsMask(FlagLS):
    REPR = 'MPLS Protocol mask'
    JSON = 'mpls-mask'
    TLV = 1094
    FLAGS = ['LDP', 'RSVP-TE', 'RSV', 'RSV', 'RSV', 'RSV', 'RSV', 'RSV']
    LEN = 1
