"""asn.py

Created by Thomas Mangin on 2010-01-15.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations
from typing import TYPE_CHECKING, Optional, Type

from struct import pack, unpack

from exabgp.protocol.resource import Resource

if TYPE_CHECKING:
    from exabgp.bgp.message.open.capability.negotiated import Negotiated

# =================================================================== ASN


class ASN(Resource):
    MAX = pow(2, 16) - 1

    # ASN encoding size constants
    SIZE_4BYTE = 4  # 4-byte ASN encoding size
    SIZE_2BYTE = 2  # 2-byte ASN encoding size

    def asn4(self) -> bool:
        return self > self.MAX

    def pack_asn(self, negotiated: Optional[Negotiated] = None) -> bytes:
        asn4 = negotiated if negotiated is not None else self.asn4()
        return pack('!L' if asn4 else '!H', self)

    @classmethod
    def unpack_asn(cls: Type[ASN], data: bytes, klass: Type[ASN]) -> ASN:
        kls = klass
        value = unpack('!L' if len(data) == cls.SIZE_4BYTE else '!H', data)[0]
        return kls(value)

    def __len__(self) -> int:
        return self.SIZE_4BYTE if self.asn4() else self.SIZE_2BYTE

    def extract(self) -> list[bytes]:
        return [pack('!L', self)]

    def trans(self) -> ASN:
        if self.asn4():
            return AS_TRANS
        return self

    def __repr__(self) -> str:
        return '%ld' % int(self)

    def __str__(self) -> str:
        return '%ld' % int(self)

    @classmethod
    def from_string(cls: Type[ASN], value: str) -> ASN:
        return cls(int(value))


AS_TRANS = ASN(23456)
