"""mup.py

Created by Takeru Hayasaka on 2023-03-13.
Copyright (c) 2023 BBSakura Networks Inc. All rights reserved.
"""

from __future__ import annotations

from typing import ClassVar, TYPE_CHECKING

from struct import pack
from struct import unpack

from exabgp.bgp.message.update.attribute.community.extended import ExtendedCommunity

if TYPE_CHECKING:
    from exabgp.bgp.message.open.capability.negotiated import Negotiated
from exabgp.util.types import Buffer

# draft-mpmz-bess-mup-safi-02
# 0                   1                   2                   3
#  0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
# |     0x0c      |     0x00      |  Direct Segment Identifier    |
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
# |              Direct Segment Identifier (cont.)                |
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+


@ExtendedCommunity.register_subtype
class MUPExtendedCommunity(ExtendedCommunity):
    COMMUNITY_TYPE: ClassVar[int] = 0x0C
    # Direct-Type Segment Identifier type
    COMMUNITY_SUBTYPE: ClassVar[int] = 0x00
    LIMIT: ClassVar[int] = 4

    def __init__(self, packed: Buffer) -> None:
        ExtendedCommunity.__init__(self, packed)

    @classmethod
    def make_mup(cls, sgid2: int, sgid4: int, transitive: bool = True) -> MUPExtendedCommunity:
        """Create MUPExtendedCommunity from semantic values."""
        type_byte = cls.COMMUNITY_TYPE if transitive else cls.COMMUNITY_TYPE | cls.NON_TRANSITIVE
        packed = pack('!BBHL', type_byte, cls.COMMUNITY_SUBTYPE, sgid2, sgid4)
        return cls(packed)

    @property
    def sgid2(self) -> int:
        value: int = unpack('!H', self._packed[2:4])[0]
        return value

    @property
    def sgid4(self) -> int:
        value: int = unpack('!L', self._packed[4:8])[0]
        return value

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, MUPExtendedCommunity):
            return False
        return (
            self.COMMUNITY_SUBTYPE == other.COMMUNITY_SUBTYPE
            and self.COMMUNITY_TYPE == other.COMMUNITY_TYPE
            and ExtendedCommunity.__eq__(self, other)
        )

    def __hash__(self) -> int:
        return hash((self.sgid2, self.sgid4))

    def __repr__(self) -> str:
        return '%s:%d:%d' % ('mup', self.sgid2, self.sgid4)

    @classmethod
    def unpack_attribute(cls, data: Buffer, negotiated: Negotiated | None = None) -> MUPExtendedCommunity:
        return cls(data[:8])
