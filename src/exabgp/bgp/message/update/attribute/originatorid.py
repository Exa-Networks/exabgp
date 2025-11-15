"""originatorid.py

Created by Thomas Mangin on 2012-07-07.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from exabgp.bgp.message.open.capability.negotiated import Negotiated

from exabgp.protocol.ip import IPv4

from exabgp.bgp.message.update.attribute.attribute import Attribute


# ============================================================== OriginatorID (3)


@Attribute.register()
class OriginatorID(Attribute, IPv4):
    ID = Attribute.CODE.ORIGINATOR_ID
    FLAG = Attribute.Flag.OPTIONAL
    CACHING = True

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, OriginatorID):
            return False
        return self.ID == other.ID and self.FLAG == other.FLAG

    def __ne__(self, other: object) -> bool:
        return not self.__eq__(other)

    def pack_attribute(self, negotiated: Negotiated = None) -> bytes:  # type: ignore[assignment]
        return self._attribute(self.ton())

    @classmethod
    def unpack_attribute(cls, data: bytes, negotiated: Negotiated) -> IPv4:
        return IPv4.unpack_ipv4(data, cls)
