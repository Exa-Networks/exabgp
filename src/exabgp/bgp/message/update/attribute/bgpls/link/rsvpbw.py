"""rsvpbw.py

Created by Evelio Vila on 2016-12-01.
Copyright (c) 2014-2017 Exa Networks. All rights reserved.
"""

from __future__ import annotations

from struct import unpack

from exabgp.bgp.message.update.attribute.bgpls.linkstate import LinkState
from exabgp.bgp.message.update.attribute.bgpls.linkstate import BaseLS


# This sub-TLV contains the maximum amount of bandwidth that can be
#   reserved in this direction on this link.  Note that for
#   oversubscription purposes, this can be greater than the bandwidth of
#   the link.
# https://tools.ietf.org/html/rfc5305#section-3.5
#
#  Units are in Bytes not Bits.
#  ----------------------------


@LinkState.register()
class RsvpBw(BaseLS):
    TLV = 1090
    REPR = 'Maximum reservable link bandwidth'
    JSON = 'maximum-reservable-link-bandwidth'
    LEN = 4

    @classmethod
    def unpack_bgpls(cls, data: bytes) -> RsvpBw:
        cls.check(data)
        return cls(unpack('!f', data)[0])
