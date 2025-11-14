"""nodename.py

Created by Evelio Vila on 2016-12-01.
Copyright (c) 2014-2017 Exa Networks. All rights reserved.
"""

from __future__ import annotations

import json
from struct import unpack

from exabgp.bgp.message.update.attribute.bgpls.linkstate import BaseLS
from exabgp.bgp.message.update.attribute.bgpls.linkstate import LinkState

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


@LinkState.register()
class NodeOpaque(BaseLS):
    TLV = 1025
    REPR = 'Node Opaque attribute'
    JSON = 'opaque'

    def __init__(self, opaque):
        BaseLS.__init__(self, opaque)

    @classmethod
    def unpack_attribute(cls, data: bytes) -> NodeOpaque:
        return cls(unpack('!%ds' % len(data), data)[0])

    def json(self, compact=None):
        return f'"{self.JSON}": {json.dumps(self.content)}'
