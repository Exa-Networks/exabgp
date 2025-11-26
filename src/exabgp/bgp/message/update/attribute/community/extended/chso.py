"""chso.py

License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from typing import ClassVar

from struct import pack
from struct import unpack

from exabgp.bgp.message.update.attribute.community.extended import ExtendedCommunity

# draft-fm-bess-service-chaining


@ExtendedCommunity.register
class ConsistentHashSortOrder(ExtendedCommunity):
    COMMUNITY_TYPE: ClassVar[int] = 0x03
    COMMUNITY_SUBTYPE: ClassVar[int] = 0x14
    DESCRIPTION: ClassVar[str] = 'consistentHashSortOrder'

    def __init__(self, order: int, reserved: int = 0, community: bytes | None = None) -> None:
        self.order: int = order
        self.reserved: int = reserved

        ExtendedCommunity.__init__(
            self,
            community if community is not None else pack('!2sIH', self._subtype(), order, reserved),
        )

    def __repr__(self) -> str:
        return '%s:%d' % (self.DESCRIPTION, self.order)

    @staticmethod
    def unpack_attribute(data: bytes) -> ConsistentHashSortOrder:
        order, reserved = unpack('!IH', data[2:8])
        return ConsistentHashSortOrder(order, reserved, data[:8])
