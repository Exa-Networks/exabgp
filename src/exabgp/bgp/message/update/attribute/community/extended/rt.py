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
        return self._packed[2 : self.LIMIT]

    @property
    def ga(self) -> bytes:
        return self._packed[self.LIMIT : 8]

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, RouteTarget):
            return False
        return self.COMMUNITY_SUBTYPE == other.COMMUNITY_SUBTYPE and ExtendedCommunity.__eq__(self, other)


# ============================================================= RouteTargetASN2Number
# RFC 4360 / RFC 7153


@ExtendedCommunity.register
class RouteTargetASN2Number(RouteTarget):
    COMMUNITY_TYPE: ClassVar[int] = 0x00
    LIMIT: ClassVar[int] = 4

    def __init__(self, packed: bytes) -> None:
        RouteTarget.__init__(self, packed)

    @classmethod
    def make_route_target(cls, asn: ASN, number: int, transitive: bool = True) -> RouteTargetASN2Number:
        """Create RouteTargetASN2Number from semantic values."""
        type_byte = cls.COMMUNITY_TYPE if transitive else cls.COMMUNITY_TYPE | cls.NON_TRANSITIVE
        packed = pack('!BBHL', type_byte, cls.COMMUNITY_SUBTYPE, asn, number)
        return cls(packed)

    @property
    def asn(self) -> ASN:
        return ASN(unpack('!H', self._packed[2:4])[0])

    @property
    def number(self) -> int:
        value: int = unpack('!L', self._packed[4:8])[0]
        return value

    def __hash__(self) -> int:
        return hash((self.asn, self.number))

    def __repr__(self) -> str:
        return '%s:%d:%d' % (self.DESCRIPTION, self.asn, self.number)

    @classmethod
    def unpack_attribute(cls, data: bytes, negotiated: Negotiated | None = None) -> RouteTargetASN2Number:
        return cls(data[:8])


# ============================================================= RouteTargetIPNumber
# RFC 4360 / RFC 7153


@ExtendedCommunity.register
class RouteTargetIPNumber(RouteTarget):
    COMMUNITY_TYPE: ClassVar[int] = 0x01
    LIMIT: ClassVar[int] = 6

    def __init__(self, packed: bytes) -> None:
        RouteTarget.__init__(self, packed)

    @classmethod
    def make_route_target(cls, ip: str, number: int, transitive: bool = True) -> RouteTargetIPNumber:
        """Create RouteTargetIPNumber from semantic values."""
        type_byte = cls.COMMUNITY_TYPE if transitive else cls.COMMUNITY_TYPE | cls.NON_TRANSITIVE
        packed = pack('!BB4sH', type_byte, cls.COMMUNITY_SUBTYPE, IPv4.pton(ip), number)
        return cls(packed)

    @property
    def ip(self) -> str:
        return IPv4.ntop(self._packed[2:6])

    @property
    def number(self) -> int:
        value: int = unpack('!H', self._packed[6:8])[0]
        return value

    def __hash__(self) -> int:
        return hash((self.ip, self.number))

    def __repr__(self) -> str:
        return '%s:%s:%d' % (self.DESCRIPTION, self.ip, self.number)

    @classmethod
    def unpack_attribute(cls, data: bytes, negotiated: Negotiated | None = None) -> RouteTargetIPNumber:
        return cls(data[:8])


# ======================================================== RouteTargetASN4Number
# RFC 4360 / RFC 7153


@ExtendedCommunity.register
class RouteTargetASN4Number(RouteTarget):
    COMMUNITY_TYPE: ClassVar[int] = 0x02
    LIMIT: ClassVar[int] = 6

    def __init__(self, packed: bytes) -> None:
        RouteTarget.__init__(self, packed)

    @classmethod
    def make_route_target(cls, asn: ASN, number: int, transitive: bool = True) -> RouteTargetASN4Number:
        """Create RouteTargetASN4Number from semantic values."""
        type_byte = cls.COMMUNITY_TYPE if transitive else cls.COMMUNITY_TYPE | cls.NON_TRANSITIVE
        packed = pack('!BBLH', type_byte, cls.COMMUNITY_SUBTYPE, asn, number)
        return cls(packed)

    @property
    def asn(self) -> ASN:
        return ASN(unpack('!L', self._packed[2:6])[0])

    @property
    def number(self) -> int:
        value: int = unpack('!H', self._packed[6:8])[0]
        return value

    def __hash__(self) -> int:
        return hash((self.asn, self.number))

    def __repr__(self) -> str:
        return '%s:%d:%d' % (self.DESCRIPTION, self.asn, self.number)

    @classmethod
    def unpack_attribute(cls, data: bytes, negotiated: Negotiated | None = None) -> RouteTargetASN4Number:
        return cls(data[:8])
