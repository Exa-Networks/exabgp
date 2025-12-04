"""prefixmetric.py

Created by Evelio Vila on 2016-12-01.
Copyright (c) 2014-2017 Exa Networks. All rights reserved.
"""

from __future__ import annotations

from struct import pack, unpack

from exabgp.bgp.message.update.attribute.bgpls.linkstate import LinkState
from exabgp.bgp.message.update.attribute.bgpls.linkstate import BaseLS

#
#      0                   1                   2                   3
#      0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
#     +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#     |              Type             |             Length            |
#     +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#     |                            Metric                             |
#     +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#     https://tools.ietf.org/html/rfc7752#section-3.3.3.4


@LinkState.register_lsid()
class PrefixMetric(BaseLS):
    TLV = 1155
    REPR = 'prefix_metric'
    JSON = 'prefix-metric'
    LEN = 4

    @property
    def content(self) -> int:
        """Unpack and return the metric value from packed bytes."""
        return int(unpack('!L', self._packed)[0])

    @classmethod
    def make_prefixmetric(cls, metric: int) -> PrefixMetric:
        """Factory method to create PrefixMetric from metric value.

        Args:
            metric: The prefix metric value (32-bit unsigned)

        Returns:
            PrefixMetric instance with packed bytes
        """
        return cls(pack('!I', metric))

    @classmethod
    def unpack_bgpls(cls, data: bytes) -> PrefixMetric:
        cls.check(data)
        return cls(data)
