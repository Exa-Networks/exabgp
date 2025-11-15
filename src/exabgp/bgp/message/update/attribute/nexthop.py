"""nexthop.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, Optional

if TYPE_CHECKING:
    from exabgp.bgp.message.open.capability.negotiated import Negotiated

from exabgp.protocol.family import AFI
from exabgp.protocol.ip import IP
from exabgp.protocol.ip import NoNextHop
from exabgp.bgp.message.update.attribute.attribute import Attribute


# ================================================================== NextHop (3)

# The inheritance order is important and attribute MUST be first for the righ register to be called
# At least until we rename them to be more explicit


@Attribute.register()
class NextHop(Attribute, IP):
    ID = Attribute.CODE.NEXT_HOP
    FLAG = Attribute.Flag.TRANSITIVE
    CACHING = True
    SELF: ClassVar[bool] = False

    # XXX: This is a bad API, as it works on non-raw data
    def __init__(self, string: str, packed: Optional[bytes] = None) -> None:
        self.init(string, packed)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, NextHop):
            return False
        return self.ID == other.ID and self.FLAG == other.FLAG and self._packed == other.ton()

    def __ne__(self, other: object) -> bool:
        return not self.__eq__(other)

    def ton(self, negotiated: Negotiated = None, afi: AFI = AFI.undefined) -> bytes:  # type: ignore[override]
        return self._packed

    def pack(self, negotiated: Negotiated) -> bytes:
        return self._attribute(self.ton())

    @classmethod
    def unpack_attribute(cls, data: bytes, negotiated: Negotiated) -> IP:
        if not data:
            return NoNextHop  # type: ignore[return-value]
        return IP.unpack_ip(data, NextHop)

    def __repr__(self) -> str:
        return IP.__repr__(self)


class NextHopSelf(NextHop):
    SELF: ClassVar[bool] = True

    def __init__(self, afi: AFI) -> None:
        self.afi: AFI = afi

    def __repr__(self) -> str:
        return 'self'

    def ipv4(self) -> bool:
        return self.afi == AFI.ipv4

    def pack(self, negotiated: Negotiated) -> bytes:
        return self._attribute(negotiated.nexthopself(self.afi).ton())

    def ton(self, negotiated: Negotiated = None, afi: AFI = AFI.undefined) -> bytes:  # type: ignore[override]
        return negotiated.nexthopself(afi).ton()  # type: ignore[no-any-return]

    def __eq__(self, other: object) -> bool:
        raise RuntimeError('do not use __eq__ with NextHop')
