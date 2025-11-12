"""origin.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from typing import Any, ClassVar, Optional

from exabgp.bgp.message.update.attribute.attribute import Attribute


# =================================================================== Origin (1)


@Attribute.register()
class Origin(Attribute):
    ID = Attribute.CODE.ORIGIN
    FLAG = Attribute.Flag.TRANSITIVE
    CACHING = True

    IGP: ClassVar[int] = 0x00
    EGP: ClassVar[int] = 0x01
    INCOMPLETE: ClassVar[int] = 0x02

    def __init__(self, origin: int, packed: Optional[bytes] = None) -> None:
        self.origin: int = origin
        self._packed: bytes = self._attribute(packed if packed else bytes([origin]))

    def __eq__(self, other: object) -> bool:
        return self.ID == other.ID and self.FLAG == other.FLAG and self.origin == other.origin  # type: ignore[attr-defined]

    def __ne__(self, other: object) -> bool:
        return not self.__eq__(other)

    def pack(self, negotiated: Any = None) -> bytes:
        return self._packed

    def __len__(self) -> int:
        return len(self._packed)

    def __repr__(self) -> str:
        if self.origin == Origin.IGP:
            return 'igp'
        if self.origin == Origin.EGP:
            return 'egp'
        if self.origin == Origin.INCOMPLETE:
            return 'incomplete'
        return 'invalid'

    @classmethod
    def unpack(cls, data: bytes, direction: int, negotiated: Any) -> Origin:
        return cls(data[0], data)

    @classmethod
    def setCache(cls) -> None:
        # there can only be three, build them now
        IGP = Origin(Origin.IGP)
        EGP = Origin(Origin.EGP)
        INC = Origin(Origin.INCOMPLETE)

        cls.cache[Attribute.CODE.ORIGIN][IGP.pack()] = IGP
        cls.cache[Attribute.CODE.ORIGIN][EGP.pack()] = EGP
        cls.cache[Attribute.CODE.ORIGIN][INC.pack()] = INC


Origin.setCache()
