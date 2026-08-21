"""nodename.py

Created by Evelio Vila on 2016-12-01.
Copyright (c) 2014-2017 Exa Networks. All rights reserved.
"""

from __future__ import annotations

import json

from exabgp.bgp.message.update.attribute.bgpls.linkstate import BaseLS
from exabgp.bgp.message.update.attribute.bgpls.linkstate import LinkState
from exabgp.util.types import Buffer

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


@LinkState.register_lsid(tlv=1025, json_key='opaque', repr_name='Node Opaque attribute')
class NodeOpaque(BaseLS):
    @classmethod
    def unpack_bgpls(cls, data: Buffer) -> NodeOpaque:
        return cls(data)

    @property
    def content(self) -> Buffer:
        """Opaque data as bytes.

        This deliberately does NOT match what json() renders, which is the hex of the same
        bytes.  content is the packed-bytes-first accessor and the tests assert it as such,
        so aligning the two here would change an accessor rather than a rendering.

        The consequence is that this class must not be marked MERGE without deciding how
        opaque bytes should reach the API first: the merge renders content through
        jsonable(), which decodes bytes as text with replacement characters, where json()
        renders hex.  TLV 1097 and 1157 already take the decoding route and lose peer data
        to U+FFFD.  Choosing one encoding for all three is a change to what a consumer
        receives and is recorded as a question rather than made here.
        """
        return self._packed

    def json(self, compact: bool = False) -> str:
        return f'"{self.JSON}": {json.dumps(self._packed.hex())}'

    @classmethod
    def make_node_opaque(cls, data: Buffer) -> NodeOpaque:
        """Create NodeOpaque from opaque data bytes.

        Args:
            data: Opaque data bytes

        Returns:
            NodeOpaque instance with packed wire-format bytes
        """
        return cls(data)
