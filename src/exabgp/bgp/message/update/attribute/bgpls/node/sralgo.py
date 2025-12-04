"""sralgo.py

Created by Evelio Vila
Copyright (c) 2014-2017 Exa Networks. All rights reserved.
"""

from __future__ import annotations

import json

from exabgp.bgp.message.update.attribute.bgpls.linkstate import BaseLS
from exabgp.bgp.message.update.attribute.bgpls.linkstate import LinkState

#     draft-gredler-idr-bgp-ls-segment-routing-ext-03
#    0                   1                   2                   3
#    0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
#   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#   |            Type               |            Length             |
#   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#   |  Algorithm 1  |  Algorithm... |  Algorithm N |                |
#   +-                                                             -+
#   |                                                               |
#   +                                                               +
# 						sec 2.1.2.


@LinkState.register_lsid()
class SrAlgorithm(BaseLS):
    TLV = 1035
    REPR = 'SrAlgorithms'
    JSON = 'sr-algorithms'

    @classmethod
    def unpack_bgpls(cls, data: bytes) -> SrAlgorithm:
        # Looks like IOS XR advertises len 0 on this sub TLV
        # when using default SPF.
        return cls(data)

    @property
    def content(self) -> list[int]:
        """List of SR algorithm values."""
        # Empty data means default SPF algorithm (0)
        return list(self._packed) or [0]

    def json(self, compact: bool = False) -> str:
        return f'"{self.JSON}": {json.dumps(self.content)}'
