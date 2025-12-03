"""localpref.py

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

# ========================================================= Local Preference (5)
#


@Attribute.register()
class LocalPreference(Attribute):
    ID = Attribute.CODE.LOCAL_PREF
    FLAG = Attribute.Flag.TRANSITIVE
    CACHING = True
    TREAT_AS_WITHDRAW = True
    MANDATORY = True

    def __init__(self, packed: bytes) -> None:
        """Initialize LocalPreference from packed wire-format bytes.

        NO validation - trusted internal use only.
        Use from_packet() for wire data or make_localpref() for semantic construction.

        Args:
            packed: Raw attribute value bytes (4-byte unsigned integer, network order)
        """
        self._packed: bytes = packed

    @classmethod
    def from_packet(cls, data: bytes) -> 'LocalPreference':
        """Validate and create from wire-format bytes.

        Args:
            data: Raw attribute value bytes from wire

        Returns:
            LocalPreference instance

        Raises:
            ValueError: If data is not exactly 4 bytes
        """
        if len(data) != 4:
            raise ValueError(f'LocalPreference requires exactly 4 bytes, got {len(data)}')
        return cls(data)

    @classmethod
    def make_localpref(cls, localpref: int) -> 'LocalPreference':
        """Create LocalPreference from semantic value with validation.

        Args:
            localpref: Local preference value (0-4294967295), higher is preferred

        Returns:
            LocalPreference instance

        Raises:
            ValueError: If localpref value is out of range
        """
        if not 0 <= localpref <= 0xFFFFFFFF:
            raise ValueError(f'LocalPreference value out of range: {localpref}')
        return cls(pack('!L', localpref))

    @property
    def localpref(self) -> int:
        """Get local preference value by unpacking from bytes."""
        return unpack('!L', self._packed)[0]

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, LocalPreference):
            return False
        return self.ID == other.ID and self.FLAG == other.FLAG and self.localpref == other.localpref

    def __ne__(self, other: object) -> bool:
        return not self.__eq__(other)

    def pack_attribute(self, negotiated: Negotiated | None = None) -> bytes:
        return self._attribute(self._packed)

    def __len__(self) -> int:
        return len(self._packed)

    def __repr__(self) -> str:
        return str(self.localpref)

    @classmethod
    def unpack_attribute(cls, data: bytes, negotiated: Negotiated) -> LocalPreference:
        # Wire data - use from_packet for validation
        return cls.from_packet(data)
