"""nodename.py

Created by Evelio Vila on 2016-12-01.
Copyright (c) 2014-2017 Exa Networks. All rights reserved.
"""

from __future__ import annotations

import json

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


@LinkState.register_lsid()
class NodeOpaque(BaseLS):
    TLV = 1025
    REPR = 'Node Opaque attribute'
    JSON = 'opaque'

    @classmethod
    def unpack_bgpls(cls, data: bytes) -> NodeOpaque:
        return cls(data)

    @property
    def content(self) -> bytes:
        """Opaque data as bytes."""
        return self._packed

    def json(self, compact: bool = False) -> str:
        return f'"{self.JSON}": {json.dumps(self._packed.hex())}'

    @classmethod
    def make_node_opaque(cls, data: bytes) -> NodeOpaque:
        """Create NodeOpaque from opaque data bytes.

        Args:
            data: Opaque data bytes

        Returns:
            NodeOpaque instance with packed wire-format bytes
        """
        return cls(data)
