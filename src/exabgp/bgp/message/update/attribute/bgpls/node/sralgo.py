"""sralgo.py

Created by Evelio Vila
Copyright (c) 2014-2017 Exa Networks. All rights reserved.
"""

from __future__ import annotations

import json

from exabgp.bgp.message.update.attribute.bgpls.linkstate import BaseLS
from exabgp.bgp.message.update.attribute.bgpls.linkstate import LinkState
from exabgp.util.types import Buffer
from exabgp.util.intvalue import json_number

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


class SrAlgorithm(BaseLS):
    @classmethod
    def unpack_bgpls(cls, data: Buffer) -> SrAlgorithm:
        # RFC 9085 2.1.3 gives a minimum of one octet, and a comment here said IOS XR sends
        # none for the default SPF.  The empty TLV is kept, as RFC 9552 8.2.2 asks of a
        # propagator, which is not to judge the length of a variable length TLV.
        return cls(data)

    @classmethod
    def make_sr_algorithm(cls, sr_algos: list[int]) -> SrAlgorithm:
        """Create SrAlgorithm from list of algorithm values.

        Args:
            sr_algos: List of SR algorithm values (each 0-255)

        Returns:
            SrAlgorithm instance with packed wire-format bytes
        """
        packed = bytes(sr_algos)
        return cls(packed)

    @property
    def content(self) -> list[int]:
        """List of SR algorithm values."""
        # Every algorithm the peer listed, and none when it listed none.  An empty TLV used
        # to be published as [0], an algorithm the peer had not sent.
        return list(self._packed)

    def json(self, compact: bool = False) -> str:
        return f'"{self.JSON}": {json.dumps(self.content, default=json_number)}'


LinkState.register_lsid(tlv=1035, json_key='sr-algorithms', repr_name='SrAlgorithms')(SrAlgorithm)
