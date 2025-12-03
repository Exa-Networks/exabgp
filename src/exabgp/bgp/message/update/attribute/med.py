"""med.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

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

        Args:
            packed: Raw attribute value bytes (4-byte unsigned integer, network order)

        Raises:
            ValueError: If packed data is not exactly 4 bytes
        """
        if len(packed) != 4:
            raise ValueError(f'MED requires exactly 4 bytes, got {len(packed)}')
        self._packed: bytes = packed

    @classmethod
    def make_med(cls, med: int) -> 'MED':
        """Create MED from semantic value.

        Args:
            med: Multi-Exit Discriminator value (0-4294967295)

        Returns:
            MED instance
        """
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
        # MED is always 4 bytes payload + 3 byte header = 7 bytes total
        return 7

    def __repr__(self) -> str:
        return str(self.med)

    def __hash__(self) -> int:
        return hash(self.med)

    @classmethod
    def unpack_attribute(cls, data: bytes, negotiated: Negotiated) -> MED:
        # Validation happens in __init__
        return cls(data)
