"""mup.py

Created by Takeru Hayasaka on 2023-03-13.
Copyright (c) 2023 BBSakura Networks Inc. All rights reserved.
"""

from __future__ import annotations

from typing import ClassVar, Optional

from struct import pack
from struct import unpack

from exabgp.bgp.message.update.attribute.community.extended import ExtendedCommunity

# draft-mpmz-bess-mup-safi-02
# 0                   1                   2                   3
#  0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
# |     0x0c      |     0x00      |  Direct Segment Identifier    |
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
# |              Direct Segment Identifier (cont.)                |
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+


@ExtendedCommunity.register
class MUPExtendedCommunity(ExtendedCommunity):
    COMMUNITY_TYPE: ClassVar[int] = 0x0C
    # Direct-Type Segment Identifier type
    COMMUNITY_SUBTYPE: ClassVar[int] = 0x00
    LIMIT: ClassVar[int] = 4

    def __init__(self, sgid2: int, sgid4: int, transitive: bool = True, community: Optional[bytes] = None) -> None:
        self.sgid2: int = sgid2
        self.sgid4: int = sgid4
        ExtendedCommunity.__init__(
            self,
            community if community else pack('!2sHL', self._subtype(transitive), sgid2, sgid4),
        )

    def __eq__(self, other: object) -> bool:
        return (
            self.COMMUNITY_SUBTYPE == other.COMMUNITY_SUBTYPE  # type: ignore[attr-defined]
            and self.COMMUNITY_TYPE == other.COMMUNITY_TYPE  # type: ignore[attr-defined]
            and ExtendedCommunity.__eq__(self, other)
        )

    def __ne__(self, other: object) -> bool:
        return not self.__eq__(other)

    def __hash__(self) -> int:
        return hash((self.sgid2, self.sgid4))

    def __repr__(self) -> str:
        return '%s:%d:%d' % ('mup', self.sgid2, self.sgid4)

    @classmethod
    def unpack(cls, data: bytes) -> MUPExtendedCommunity:
        sgid2, sgid4 = unpack('!HL', data[2:8])
        return MUPExtendedCommunity(sgid2, sgid4, False, data[:8])
