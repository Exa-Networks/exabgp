"""temetric.py

Created by Evelio Vila on 2016-12-01.
Copyright (c) 2014-2017 Exa Networks. All rights reserved.
"""

from __future__ import annotations

from struct import pack, unpack

from exabgp.bgp.message.update.attribute.bgpls.linkstate import LinkState
from exabgp.bgp.message.update.attribute.bgpls.linkstate import BaseLS
from exabgp.util.types import Buffer


#     0                   1                   2                   3
#     0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
#    +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#    |              Type             |             Length            |
#    +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#    |                    TE Default Link Metric                     |
#    +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#    https://tools.ietf.org/html/rfc7752#section-3.3.2.3 TE Metric


@LinkState.register_lsid()
class TeMetric(BaseLS):
    TLV = 1092
    REPR = 'TE Default Metric'
    JSON = 'te-metric'
    LEN = 4

    @property
    def content(self) -> int:
        """Unpack and return the TE metric from packed bytes."""
        value: int = unpack('!L', self._packed)[0]
        return value

    @classmethod
    def make_temetric(cls, metric: int) -> TeMetric:
        """Factory method to create TeMetric from metric value."""
        return cls(pack('!I', metric))

    @classmethod
    def unpack_bgpls(cls, data: Buffer) -> TeMetric:
        cls.check(data)
        return cls(data)
