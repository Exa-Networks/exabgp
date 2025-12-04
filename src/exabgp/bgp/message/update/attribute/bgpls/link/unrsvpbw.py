"""nunrsvpbw.py

Created by Evelio Vila on 2016-12-01.
Copyright (c) 2014-2017 Exa Networks. All rights reserved.
"""

from __future__ import annotations

from struct import pack, unpack
from typing import Sequence

from exabgp.bgp.message.update.attribute.bgpls.linkstate import LinkState
from exabgp.bgp.message.update.attribute.bgpls.linkstate import BaseLS


#   This sub-TLV contains the amount of bandwidth reservable in this
#   direction on this link.  Note that for oversubscription purposes,
#   this can be greater than the bandwidth of the link.
#    [ One value per priority]
#   https://tools.ietf.org/html/rfc5305#section-3.6
#
#  Units are in Bytes not Bits.
#  ----------------------------


@LinkState.register_lsid()
class UnRsvpBw(BaseLS):
    TLV = 1091
    REPR = 'Maximum link bandwidth'
    JSON = 'unreserved-bandwidth'
    LEN = 32

    @property
    def content(self) -> list[float]:
        """Unpack and return the 8 priority-level bandwidths from packed bytes."""
        return list(unpack('!ffffffff', self._packed))

    @classmethod
    def make_unrsvpbw(cls, bandwidths: Sequence[float]) -> UnRsvpBw:
        """Factory method to create UnRsvpBw from 8 bandwidth values."""
        if len(bandwidths) != 8:
            raise ValueError('UnRsvpBw requires exactly 8 bandwidth values')
        return cls(pack('!ffffffff', *bandwidths))

    @classmethod
    def unpack_bgpls(cls, data: bytes) -> UnRsvpBw:
        cls.check(data)
        return cls(data)
