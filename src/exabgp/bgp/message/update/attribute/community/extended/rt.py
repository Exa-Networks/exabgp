"""rt.py

Created by Thomas Mangin on 2014-06-20.
Copyright (c) 2014-2017 Orange. All rights reserved.
Copyright (c) 2014-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

if TYPE_CHECKING:
    from exabgp.bgp.message.open.capability.negotiated import Negotiated

from struct import pack
from struct import unpack

from exabgp.protocol.ip import IPv4
from exabgp.bgp.message.open.asn import ASN
from exabgp.bgp.message.update.attribute.community.extended import ExtendedCommunity


# ================================================================== RouteTarget
# RFC 4360 / RFC 7153


class RouteTarget(ExtendedCommunity):
    COMMUNITY_SUBTYPE: ClassVar[int] = 0x02
    LIMIT: ClassVar[int] = 0
    DESCRIPTION: ClassVar[str] = 'target'

    @property
    def la(self) -> bytes:
        return self.community[2 : self.LIMIT]

    @property
    def ga(self) -> bytes:
        return self.community[self.LIMIT : 8]

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, RouteTarget):
            return NotImplemented
        return self.COMMUNITY_SUBTYPE == other.COMMUNITY_SUBTYPE and ExtendedCommunity.__eq__(self, other)

    def __ne__(self, other: object) -> bool:
        return not self.__eq__(other)


# ============================================================= RouteTargetASN2Number
# RFC 4360 / RFC 7153


@ExtendedCommunity.register
class RouteTargetASN2Number(RouteTarget):
    COMMUNITY_TYPE: ClassVar[int] = 0x00
    LIMIT: ClassVar[int] = 4

    def __init__(self, asn: ASN, number: int, transitive: bool = True, community: bytes | None = None) -> None:
        self.asn: ASN = asn
        self.number: int = number
        # assert(number < pow(2,32))
        RouteTarget.__init__(self, community if community else pack('!2sHL', self._subtype(transitive), asn, number))

    def __hash__(self) -> int:
        return hash((self.asn, self.number))

    def __repr__(self) -> str:
        return '%s:%d:%d' % (self.DESCRIPTION, self.asn, self.number)

    @classmethod
    def unpack_attribute(cls, data: bytes, negotiated: Negotiated | None = None) -> RouteTargetASN2Number:
        asn, number = unpack('!HL', data[2:8])
        return cls(ASN(asn), number, False, data[:8])


# ============================================================= RouteTargetIPNumber
# RFC 4360 / RFC 7153


@ExtendedCommunity.register
class RouteTargetIPNumber(RouteTarget):
    COMMUNITY_TYPE: ClassVar[int] = 0x01
    LIMIT: ClassVar[int] = 6

    def __init__(self, ip: str, number: int, transitive: bool = True, community: bytes | None = None) -> None:
        self.ip: str = ip
        self.number: int = number
        # assert(number < pow(2,16))
        RouteTarget.__init__(
            self,
            community if community else pack('!2s4sH', self._subtype(transitive), IPv4.pton(ip), number),
        )

    # why could we not simply use ExtendedCommunity.hash ?
    def __hash__(self) -> int:
        return hash((self.ip, self.number))

    def __repr__(self) -> str:
        return '%s:%s:%d' % (self.DESCRIPTION, self.ip, self.number)

    @classmethod
    def unpack_attribute(cls, data: bytes, negotiated: Negotiated | None = None) -> RouteTargetIPNumber:
        ip, number = unpack('!4sH', data[2:8])
        return cls(IPv4.ntop(ip), number, False, data[:8])


# ======================================================== RouteTargetASN4Number
# RFC 4360 / RFC 7153


@ExtendedCommunity.register
class RouteTargetASN4Number(RouteTarget):
    COMMUNITY_TYPE: ClassVar[int] = 0x02
    LIMIT: ClassVar[int] = 6

    def __init__(self, asn: ASN, number: int, transitive: bool = True, community: bytes | None = None) -> None:
        self.asn: ASN = asn
        self.number: int = number
        # assert(number < pow(2,16))
        RouteTarget.__init__(self, community if community else pack('!2sLH', self._subtype(transitive), asn, number))

    # why could we not simply use ExtendedCommunity.hash ?
    def __hash__(self) -> int:
        return hash((self.asn, self.number))

    def __repr__(self) -> str:
        return '%s:%d:%d' % (self.DESCRIPTION, self.asn, self.number)

    @classmethod
    def unpack_attribute(cls, data: bytes, negotiated: Negotiated | None = None) -> RouteTargetASN4Number:
        asn, number = unpack('!LH', data[2:8])
        return cls(ASN(asn), number, False, data[:8])
