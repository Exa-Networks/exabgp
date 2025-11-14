"""localpref.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from struct import pack
from struct import unpack
from typing import TYPE_CHECKING, Optional

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

    def __init__(self, localpref: int, packed: Optional[bytes] = None) -> None:
        self.localpref: int = localpref
        self._packed: bytes = self._attribute(packed if packed is not None else pack('!L', localpref))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, LocalPreference):
            return False
        return self.ID == other.ID and self.FLAG == other.FLAG and self.localpref == other.localpref

    def __ne__(self, other: object) -> bool:
        return not self.__eq__(other)

    def pack(self, negotiated: Optional[Negotiated] = None) -> bytes:
        return self._packed

    def __len__(self) -> int:
        return 4

    def __repr__(self) -> str:
        return str(self.localpref)

    @classmethod
    def unpack(cls, data: bytes, negotiated: Negotiated) -> LocalPreference:
        return cls(unpack('!L', data)[0], data)
