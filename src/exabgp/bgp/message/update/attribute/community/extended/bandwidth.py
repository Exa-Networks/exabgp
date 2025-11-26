"""bandwidth.py

Created by Thomas Mangin on 2017-07-02.
Copyright (c) 2014-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from typing import ClassVar, TYPE_CHECKING

from struct import pack
from struct import unpack

from exabgp.bgp.message.update.attribute.community.extended import ExtendedCommunity

if TYPE_CHECKING:
    from exabgp.bgp.message.open.capability.negotiated import Negotiated

# ==================================================================== Bandwidth
# draft-ietf-idr-link-bandwidth-06


@ExtendedCommunity.register
class Bandwidth(ExtendedCommunity):
    COMMUNITY_TYPE: ClassVar[int] = 0x40
    COMMUNITY_SUBTYPE: ClassVar[int] = 0x04

    def __init__(self, asn: int, speed: float, community: bytes | None = None) -> None:
        self.asn: int = asn
        self.speed: float = speed
        ExtendedCommunity.__init__(self, community if community is not None else pack('!Hf', asn, speed))

    def __repr__(self) -> str:
        return 'bandwith:%d:%0.f' % (self.asn, self.speed)

    @staticmethod
    def unpack_attribute(data: bytes, negotiated: Negotiated) -> Bandwidth:
        asn, speed = unpack('!Hf', data[2:8])
        return Bandwidth(asn, speed, data[:8])
