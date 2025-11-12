"""originatorid.py

Created by Thomas Mangin on 2012-07-07.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from typing import Any

from exabgp.protocol.ip import IPv4

from exabgp.bgp.message.update.attribute.attribute import Attribute


# ============================================================== OriginatorID (3)


@Attribute.register()
class OriginatorID(Attribute, IPv4):
    ID = Attribute.CODE.ORIGINATOR_ID
    FLAG = Attribute.Flag.OPTIONAL
    CACHING = True

    def __eq__(self, other: object) -> bool:
        return self.ID == other.ID and self.FLAG == other.FLAG  # type: ignore[attr-defined]

    def __ne__(self, other: object) -> bool:
        return not self.__eq__(other)

    def pack(self, negotiated: Any = None) -> bytes:
        return self._attribute(self.ton())

    @classmethod
    def unpack(cls, data: bytes, direction: int, negotiated: Any) -> IPv4:
        return IPv4.unpack(data, cls)  # type: ignore[return-value]
