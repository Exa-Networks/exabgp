"""maxbw.py

Created by Evelio Vila on 2016-12-01.
Copyright (c) 2014-2017 Exa Networks. All rights reserved.
"""

from __future__ import annotations

from struct import pack, unpack

from exabgp.bgp.message.update.attribute.bgpls.linkstate import LinkState
from exabgp.bgp.message.update.attribute.bgpls.linkstate import BaseLS
from exabgp.util.types import Buffer

#  This sub-TLV contains the maximum bandwidth that can be used on this
#   link in this direction (from the system originating the LSP to its
#   neighbors).
#    https://tools.ietf.org/html/rfc5305#section-3.4
#
#  Units are in Bytes not Bits.
#  ----------------------------


@LinkState.register_lsid()
class MaxBw(BaseLS):
    TLV = 1089
    REPR = 'Maximum link bandwidth'
    JSON = 'maximum-link-bandwidth'
    LEN = 4

    @property
    def content(self) -> float:
        """Unpack and return the max bandwidth from packed bytes."""
        value: float = unpack('!f', self._packed)[0]
        return value

    @classmethod
    def make_maxbw(cls, bandwidth: float) -> MaxBw:
        """Factory method to create MaxBw from bandwidth value."""
        return cls(pack('!f', bandwidth))

    @classmethod
    def unpack_bgpls(cls, data: Buffer) -> MaxBw:
        cls.check(data)
        return cls(data)
