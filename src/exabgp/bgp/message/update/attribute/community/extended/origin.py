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

from exabgp.protocol.ip import IPv4
from exabgp.bgp.message.open.asn import ASN
from exabgp.bgp.message.update.attribute.community.extended import ExtendedCommunity


# ======================================================================= Origin
# RFC 4360 / RFC 7153


class Origin(ExtendedCommunity):
    COMMUNITY_SUBTYPE: ClassVar[int] = 0x03
    LIMIT: ClassVar[int] = 0  # This is to prevent warnings from scrutinizer

    @property
    def la(self) -> bytes:
        return self.community[2 : self.LIMIT]

    @property
    def ga(self) -> bytes:
        return self.community[self.LIMIT : 8]

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

    def __init__(self, asn: ASN, ip: str, transitive: bool, community: bytes | None = None) -> None:
        self.asn: ASN = asn
        self.ip: str = ip
        Origin.__init__(self, community if community else pack('!2sH4s', self._subtype(), asn, IPv4.pton(ip)))

    def __repr__(self) -> str:
        return 'origin:{}:{}'.format(self.asn, self.ip)

    @classmethod
    def unpack_attribute(cls, data: bytes, negotiated: Negotiated | None = None) -> OriginASNIP:
        asn, ip = unpack('!H4s', data[2:8])
        return cls(ASN(asn), IPv4.ntop(ip), False, data[:8])


# ================================================================== OriginIPASN
# RFC 4360 / RFC 7153


@ExtendedCommunity.register
class OriginIPASN(Origin):
    COMMUNITY_TYPE: ClassVar[int] = 0x01
    LIMIT: ClassVar[int] = 6

    def __init__(self, ip: str, asn: ASN, transitive: bool, community: bytes | None = None) -> None:
        self.ip: str = ip
        self.asn: ASN = asn
        Origin.__init__(self, community if community else pack('!2s4sH', self._subtype(), IPv4.pton(ip), asn))

    def __repr__(self) -> str:
        return 'origin:{}:{}'.format(self.ip, self.asn)

    @classmethod
    def unpack_attribute(cls, data: bytes, negotiated: Negotiated | None = None) -> OriginIPASN:
        ip, asn = unpack('!4sH', data[2:8])
        return cls(IPv4.ntop(ip), ASN(asn), False, data[:8])


# ============================================================= OriginASN4Number
# RFC 4360 / RFC 7153


@ExtendedCommunity.register
class OriginASN4Number(Origin):
    COMMUNITY_TYPE: ClassVar[int] = 0x02
    LIMIT: ClassVar[int] = 6

    def __init__(self, asn: ASN, number: int, transitive: bool, community: bytes | None = None) -> None:
        self.asn: ASN = asn
        self.number: int = number
        Origin.__init__(self, community if community else pack('!2sLH', self._subtype(), asn, number))

    def __repr__(self) -> str:
        return 'origin:{}:{}'.format(self.asn, self.number)

    @classmethod
    def unpack_attribute(cls, data: bytes, negotiated: Negotiated | None = None) -> OriginASN4Number:
        asn, number = unpack('!LH', data[2:8])
        return cls(ASN(asn), number, False, data[:8])
