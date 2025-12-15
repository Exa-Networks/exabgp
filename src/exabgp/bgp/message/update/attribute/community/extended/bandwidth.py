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
from exabgp.util.types import Buffer

# ==================================================================== Bandwidth
# draft-ietf-idr-link-bandwidth-06


@ExtendedCommunity.register
class Bandwidth(ExtendedCommunity):
    COMMUNITY_TYPE: ClassVar[int] = 0x40
    COMMUNITY_SUBTYPE: ClassVar[int] = 0x04

    def __init__(self, packed: Buffer) -> None:
        ExtendedCommunity.__init__(self, packed)

    @classmethod
    def make_bandwidth(cls, asn: int, speed: float) -> Bandwidth:
        """Create Bandwidth from semantic values."""
        packed = pack('!BBHf', cls.COMMUNITY_TYPE, cls.COMMUNITY_SUBTYPE, asn, speed)
        return cls(packed)

    @property
    def asn(self) -> int:
        value: int = unpack('!H', self._packed[2:4])[0]
        return value

    @property
    def speed(self) -> float:
        value: float = unpack('!f', self._packed[4:8])[0]
        return value

    def __repr__(self) -> str:
        return 'bandwith:%d:%0.f' % (self.asn, self.speed)

    @classmethod
    def unpack_attribute(cls, data: Buffer, negotiated: Negotiated | None = None) -> Bandwidth:
        return cls(data[:8])
