"""med.py

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

# ====================================================================== MED (4)
#


@Attribute.register()
class MED(Attribute):
    ID = Attribute.CODE.MED
    FLAG = Attribute.Flag.OPTIONAL
    CACHING = True
    TREAT_AS_WITHDRAW = True

    def __init__(self, med: int, packed: Optional[bytes] = None) -> None:
        self.med: int = med
        self._packed: bytes = self._attribute(packed if packed is not None else pack('!L', med))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, MED):
            return False
        return self.ID == other.ID and self.FLAG == other.FLAG and self.med == other.med

    def __ne__(self, other: object) -> bool:
        return not self.__eq__(other)

    def pack_attribute(self, negotiated: Optional[Negotiated] = None) -> bytes:
        return self._packed

    def __len__(self) -> int:
        return 4

    def __repr__(self) -> str:
        return str(self.med)

    def __hash__(self) -> int:
        return hash(self.med)

    @classmethod
    def unpack_attribute(cls, data: bytes, negotiated: Negotiated) -> MED:
        return cls(unpack('!L', data)[0])
