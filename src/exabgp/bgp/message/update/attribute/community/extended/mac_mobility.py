"""mac_mobility.py

Created by Anton Aksola on 2018-11-03
"""

from __future__ import annotations

from typing import ClassVar, TYPE_CHECKING

from struct import pack
from struct import unpack

from exabgp.bgp.message.update.attribute.community.extended import ExtendedCommunity

if TYPE_CHECKING:
    from exabgp.bgp.message.open.capability.negotiated import Negotiated

# ================================================================== MacMobility
# RFC 7432 Section 7.7.


@ExtendedCommunity.register
class MacMobility(ExtendedCommunity):
    COMMUNITY_TYPE: ClassVar[int] = 0x06
    COMMUNITY_SUBTYPE: ClassVar[int] = 0x00
    DESCRIPTION: ClassVar[str] = 'mac-mobility'

    def __init__(self, packed: bytes) -> None:
        ExtendedCommunity.__init__(self, packed)

    @classmethod
    def make_mac_mobility(cls, sequence: int, sticky: bool = False) -> MacMobility:
        """Create MacMobility from semantic values."""
        packed = pack('!BBBxI', cls.COMMUNITY_TYPE, cls.COMMUNITY_SUBTYPE, 1 if sticky else 0, sequence)
        return cls(packed)

    @property
    def sequence(self) -> int:
        value: int = unpack('!I', self._packed[4:8])[0]
        return value

    @property
    def sticky(self) -> bool:
        return self._packed[2] == 1

    def __hash__(self) -> int:
        return hash((self.sticky, self.sequence))

    def __repr__(self) -> str:
        s = '%s:%d' % (self.DESCRIPTION, self.sequence)
        if self.sticky:
            s += ':sticky'
        return s

    @classmethod
    def unpack_attribute(cls, data: bytes, negotiated: Negotiated | None = None) -> MacMobility:
        return cls(data[:8])
