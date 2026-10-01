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

    # written out: mypyc fails to derive __ne__ from __eq__ for the subclasses. The operator,
    # not a call to __eq__, so NotImplemented is answered the way Python answers it.
    def __ne__(self, other: object) -> bool:
        return not self == other


# ============================================================= OriginASN2Number
# RFC 4360 3.1 and RFC 7153: a two octet AS and a four octet number. The number was read
# as an IPv4 address, so origin:65001:100 printed as origin:65001:0.0.0.100.


class OriginASN2Number(Origin):
    COMMUNITY_TYPE: ClassVar[int] = 0x00
    LIMIT: ClassVar[int] = 4

    def __init__(self, packed: Buffer) -> None:
        Origin.__init__(self, packed)

    @classmethod
    def make_origin(cls, asn: ASN | int, number: int, transitive: bool = True) -> OriginASN2Number:
        """Create OriginASN2Number from semantic values."""
        type_byte = cls.COMMUNITY_TYPE if transitive else cls.COMMUNITY_TYPE | cls.NON_TRANSITIVE
        packed = pack('!BBHL', type_byte, cls.COMMUNITY_SUBTYPE, int(asn), number)
        return cls(packed)

    @property
    def asn(self) -> ASN:
        return ASN(unpack('!H', self._packed[2:4])[0])

    @property
    def number(self) -> int:
        value: int = unpack('!L', self._packed[4:8])[0]
        return value

    def __repr__(self) -> str:
        return 'origin:{}:{}'.format(self.asn, self.number)

    @classmethod
    def unpack_attribute(cls, data: Buffer, negotiated: Negotiated | None = None) -> OriginASN2Number:
        return cls(data[:8])


ExtendedCommunity.register_subtype(OriginASN2Number)


# ================================================================== OriginIPASN
# RFC 4360 / RFC 7153


class OriginIPASN(Origin):
    COMMUNITY_TYPE: ClassVar[int] = 0x01
    LIMIT: ClassVar[int] = 6

    def __init__(self, packed: Buffer) -> None:
        Origin.__init__(self, packed)

    @classmethod
    def make_origin(cls, ip: str, asn: ASN | int, transitive: bool = True) -> OriginIPASN:
        """Create OriginIPASN from semantic values."""
        type_byte = cls.COMMUNITY_TYPE if transitive else cls.COMMUNITY_TYPE | cls.NON_TRANSITIVE
        packed = pack('!BB4sH', type_byte, cls.COMMUNITY_SUBTYPE, IPv4.pton(ip), int(asn))
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


ExtendedCommunity.register_subtype(OriginIPASN)


# ============================================================= OriginASN4Number
# RFC 4360 / RFC 7153


class OriginASN4Number(Origin):
    COMMUNITY_TYPE: ClassVar[int] = 0x02
    LIMIT: ClassVar[int] = 6

    def __init__(self, packed: Buffer) -> None:
        Origin.__init__(self, packed)

    @classmethod
    def make_origin(cls, asn: ASN | int, number: int, transitive: bool = True) -> OriginASN4Number:
        """Create OriginASN4Number from semantic values."""
        type_byte = cls.COMMUNITY_TYPE if transitive else cls.COMMUNITY_TYPE | cls.NON_TRANSITIVE
        packed = pack('!BBLH', type_byte, cls.COMMUNITY_SUBTYPE, int(asn), number)
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


ExtendedCommunity.register_subtype(OriginASN4Number)
