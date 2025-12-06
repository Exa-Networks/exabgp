"""med.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from collections.abc import Buffer
from struct import pack
from struct import unpack
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from exabgp.bgp.message.open.capability.negotiated import Negotiated

from exabgp.bgp.message.update.attribute.attribute import Attribute

# ====================================================================== MED (4)
#


@Attribute.register()
class MED(Attribute):
    ID = Attribute.CODE.MED
    FLAG = Attribute.Flag.OPTIONAL
    CACHING = True
    TREAT_AS_WITHDRAW = True

    def __init__(self, packed: bytes) -> None:
        """Initialize MED from packed wire-format bytes.

        NO validation - trusted internal use only.
        Use from_packet() for wire data or make_med() for semantic construction.

        Args:
            packed: Raw attribute value bytes (4-byte unsigned integer, network order)
        """
        self._packed: bytes = packed

    @classmethod
    def from_packet(cls, data: Buffer) -> 'MED':
        """Validate and create from wire-format bytes.

        Args:
            data: Raw attribute value bytes from wire

        Returns:
            MED instance

        Raises:
            ValueError: If data is not exactly 4 bytes
        """
        data_bytes = bytes(data)
        if len(data_bytes) != 4:
            raise ValueError(f'MED requires exactly 4 bytes, got {len(data_bytes)}')
        return cls(data_bytes)

    @classmethod
    def from_int(cls, med: int) -> 'MED':
        """Create MED from semantic value with validation.

        Args:
            med: Multi-Exit Discriminator value (0-4294967295)

        Returns:
            MED instance

        Raises:
            ValueError: If med value is out of range
        """
        if not 0 <= med <= 0xFFFFFFFF:
            raise ValueError(f'MED value out of range: {med}')
        return cls(pack('!L', med))

    @property
    def med(self) -> int:
        """Get MED value by unpacking from bytes."""
        return unpack('!L', self._packed)[0]

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, MED):
            return False
        return self.ID == other.ID and self.FLAG == other.FLAG and self.med == other.med

    def __ne__(self, other: object) -> bool:
        return not self.__eq__(other)

    def pack_attribute(self, negotiated: Negotiated | None = None) -> bytes:
        return self._attribute(self._packed)

    def __len__(self) -> int:
        return len(self._packed)

    def __repr__(self) -> str:
        return str(self.med)

    def __hash__(self) -> int:
        return hash(self.med)

    @classmethod
    def unpack_attribute(cls, data: Buffer, negotiated: Negotiated) -> MED:
        # Wire data - use from_packet for validation
        return cls.from_packet(data)
