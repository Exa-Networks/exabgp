"""mac_mobility.py

Created by Anton Aksola on 2018-11-03
"""

from __future__ import annotations

from typing import ClassVar, Optional

from struct import pack
from struct import unpack

from exabgp.bgp.message.update.attribute.community.extended import ExtendedCommunity

# ================================================================== MacMobility
# RFC 7432 Section 7.7.


@ExtendedCommunity.register
class MacMobility(ExtendedCommunity):
    COMMUNITY_TYPE: ClassVar[int] = 0x06
    COMMUNITY_SUBTYPE: ClassVar[int] = 0x00
    DESCRIPTION: ClassVar[str] = 'mac-mobility'

    def __init__(self, sequence: int, sticky: bool = False, community: Optional[bytes] = None) -> None:
        self.sequence: int = sequence
        self.sticky: bool = sticky
        ExtendedCommunity.__init__(
            self,
            community if community else pack('!2sBxI', self._subtype(transitive=True), 1 if sticky else 0, sequence),
        )

    def __hash__(self) -> int:
        return hash((self.sticky, self.sequence))

    def __repr__(self) -> str:
        s = '%s:%d' % (self.DESCRIPTION, self.sequence)
        if self.sticky:
            s += ':sticky'
        return s

    @staticmethod
    def unpack(data: bytes) -> MacMobility:
        flags, seq = unpack('!BxI', data[2:8])
        return MacMobility(seq, flags == 1)
