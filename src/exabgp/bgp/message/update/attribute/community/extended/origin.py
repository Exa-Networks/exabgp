"""origin.py

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

from exabgp.util.types import Buffer

from exabgp.protocol.ip import IPv4
from exabgp.bgp.message.open.asn import ASN
from exabgp.bgp.message.update.attribute.community.extended import ExtendedCommunity


# ======================================================================= Origin
# RFC 4360 / RFC 7153


class Origin(ExtendedCommunity):
    COMMUNITY_SUBTYPE: ClassVar[int] = 0x03
    LIMIT: ClassVar[int] = 0  # This is to prevent warnings from scrutinizer

    @property
    def la(self) -> Buffer:
        return self._packed[2 : self.LIMIT]

    @property
    def ga(self) -> Buffer:
        return self._packed[self.LIMIT : 8]

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Origin):
            return False
        return self.COMMUNITY_SUBTYPE == other.COMMUNITY_SUBTYPE and ExtendedCommunity.__eq__(self, other)


# ================================================================== OriginASNIP
# RFC 4360 / RFC 7153


@ExtendedCommunity.register
class OriginASNIP(Origin):
    COMMUNITY_TYPE: ClassVar[int] = 0x00
    LIMIT: ClassVar[int] = 4

    def __init__(self, packed: Buffer) -> None:
        Origin.__init__(self, packed)

    @classmethod
    def make_origin(cls, asn: ASN, ip: str, transitive: bool = True) -> OriginASNIP:
        """Create OriginASNIP from semantic values."""
        type_byte = cls.COMMUNITY_TYPE if transitive else cls.COMMUNITY_TYPE | cls.NON_TRANSITIVE
        packed = pack('!BBH4s', type_byte, cls.COMMUNITY_SUBTYPE, asn, IPv4.pton(ip))
        return cls(packed)

    @property
    def asn(self) -> ASN:
        return ASN(unpack('!H', self._packed[2:4])[0])

    @property
    def ip(self) -> str:
        return IPv4.ntop(self._packed[4:8])

    def __repr__(self) -> str:
        return 'origin:{}:{}'.format(self.asn, self.ip)

    @classmethod
    def unpack_attribute(cls, data: Buffer, negotiated: Negotiated | None = None) -> OriginASNIP:
        return cls(data[:8])


# ================================================================== OriginIPASN
# RFC 4360 / RFC 7153


@ExtendedCommunity.register
class OriginIPASN(Origin):
    COMMUNITY_TYPE: ClassVar[int] = 0x01
    LIMIT: ClassVar[int] = 6

    def __init__(self, packed: Buffer) -> None:
        Origin.__init__(self, packed)

    @classmethod
    def make_origin(cls, ip: str, asn: ASN, transitive: bool = True) -> OriginIPASN:
        """Create OriginIPASN from semantic values."""
        type_byte = cls.COMMUNITY_TYPE if transitive else cls.COMMUNITY_TYPE | cls.NON_TRANSITIVE
        packed = pack('!BB4sH', type_byte, cls.COMMUNITY_SUBTYPE, IPv4.pton(ip), asn)
        return cls(packed)

    @property
    def ip(self) -> str:
        return IPv4.ntop(self._packed[2:6])

    @property
    def asn(self) -> ASN:
        return ASN(unpack('!H', self._packed[6:8])[0])

    def __repr__(self) -> str:
        return 'origin:{}:{}'.format(self.ip, self.asn)

    @classmethod
    def unpack_attribute(cls, data: Buffer, negotiated: Negotiated | None = None) -> OriginIPASN:
        return cls(data[:8])


# ============================================================= OriginASN4Number
# RFC 4360 / RFC 7153


@ExtendedCommunity.register
class OriginASN4Number(Origin):
    COMMUNITY_TYPE: ClassVar[int] = 0x02
    LIMIT: ClassVar[int] = 6

    def __init__(self, packed: Buffer) -> None:
        Origin.__init__(self, packed)

    @classmethod
    def make_origin(cls, asn: ASN, number: int, transitive: bool = True) -> OriginASN4Number:
        """Create OriginASN4Number from semantic values."""
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

    def __repr__(self) -> str:
        return 'origin:{}:{}'.format(self.asn, self.number)

    @classmethod
    def unpack_attribute(cls, data: Buffer, negotiated: Negotiated | None = None) -> OriginASN4Number:
        return cls(data[:8])
