"""chso.py

License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

if TYPE_CHECKING:
    from exabgp.bgp.message.open.capability.negotiated import Negotiated

from struct import pack
from struct import unpack

from exabgp.bgp.message.update.attribute.community.extended import ExtendedCommunity
from exabgp.util.types import Buffer

# draft-fm-bess-service-chaining


@ExtendedCommunity.register_subtype
class ConsistentHashSortOrder(ExtendedCommunity):
    COMMUNITY_TYPE: ClassVar[int] = 0x03
    COMMUNITY_SUBTYPE: ClassVar[int] = 0x14
    DESCRIPTION: ClassVar[str] = 'consistentHashSortOrder'

    def __init__(self, packed: Buffer) -> None:
        ExtendedCommunity.__init__(self, packed)

    @classmethod
    def make_chso(cls, order: int, reserved: int = 0) -> ConsistentHashSortOrder:
        """Create ConsistentHashSortOrder from semantic values."""
        packed = pack('!BBIH', cls.COMMUNITY_TYPE, cls.COMMUNITY_SUBTYPE, order, reserved)
        return cls(packed)

    @property
    def order(self) -> int:
        value: int = unpack('!I', self._packed[2:6])[0]
        return value

    @property
    def reserved(self) -> int:
        value: int = unpack('!H', self._packed[6:8])[0]
        return value

    def __repr__(self) -> str:
        return '%s:%d' % (self.DESCRIPTION, self.order)

    @classmethod
    def unpack_attribute(cls, data: Buffer, negotiated: Negotiated | None = None) -> ConsistentHashSortOrder:
        return cls(data[:8])
