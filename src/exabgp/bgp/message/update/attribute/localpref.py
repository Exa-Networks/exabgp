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

        Args:
            packed: Raw attribute value bytes (4-byte unsigned integer, network order)
        """
        self._packed: bytes = packed

    @classmethod
    def make_localpref(cls, localpref: int) -> 'LocalPreference':
        """Create LocalPreference from semantic value.

        Args:
            localpref: Local preference value (0-4294967295), higher is preferred

        Returns:
            LocalPreference instance
        """
        return cls(pack('!L', localpref))

    @property
    def localpref(self) -> int:
        """Get local preference value by unpacking from bytes."""
        if len(self._packed) != 4:
            raise IndexError('LocalPreference has invalid data length')
        return unpack('!L', self._packed)[0]

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, LocalPreference):
            return False
        if len(self._packed) != 4 or len(other._packed) != 4:
            return self._packed == other._packed
        return self.ID == other.ID and self.FLAG == other.FLAG and self.localpref == other.localpref

    def __ne__(self, other: object) -> bool:
        return not self.__eq__(other)

    def pack_attribute(self, negotiated: Negotiated | None = None) -> bytes:
        return self._attribute(self._packed)

    def __len__(self) -> int:
        # LocalPreference is always 4 bytes payload + 3 byte header = 7 bytes total
        return 7

    def __repr__(self) -> str:
        if len(self._packed) != 4:
            return 'invalid'
        return str(self.localpref)

    @classmethod
    def unpack_attribute(cls, data: bytes, negotiated: Negotiated) -> LocalPreference:
        if len(data) != 4:
            from exabgp.bgp.message.notification import Notify

            raise Notify(3, 5, f'LocalPreference attribute has invalid length {len(data)}, expected 4')
        return cls(data)
