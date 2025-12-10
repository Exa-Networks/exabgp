"""asn.py

Created by Thomas Mangin on 2010-01-15.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from exabgp.util.types import Buffer
from struct import pack, unpack
from typing import Type

from exabgp.protocol.resource import Resource

# =================================================================== ASN


class ASN(Resource):
    MAX_2BYTE = pow(2, 16) - 1  # Maximum 16-bit ASN value
    MAX_4BYTE = pow(2, 32) - 1  # Maximum 32-bit ASN value

    # ASN encoding size constants
    SIZE_4BYTE = 4  # 4-byte ASN encoding size
    SIZE_2BYTE = 2  # 2-byte ASN encoding size

    def asn4(self) -> bool:
        return self > self.MAX_2BYTE

    def pack_asn2(self) -> bytes:
        return pack('!H', self)

    def pack_asn4(self) -> bytes:
        return pack('!L', self)

    def pack_asn(self, asn4: bool) -> bytes:
        return pack('!L' if asn4 else '!H', self)

    @classmethod
    def unpack_asn(cls: Type[ASN], data: Buffer, klass: Type[ASN]) -> ASN:
        kls = klass
        if len(data) == cls.SIZE_4BYTE:
            value = unpack('!L', data)[0]
        elif len(data) == cls.SIZE_2BYTE:
            value = unpack('!H', data)[0]
        else:
            raise ValueError(f'ASN data invalid size: need {cls.SIZE_2BYTE} or {cls.SIZE_4BYTE} bytes, got {len(data)}')
        return kls(value)

    def __len__(self) -> int:
        return self.SIZE_4BYTE if self.asn4() else self.SIZE_2BYTE

    def extract_asn_bytes(self) -> list[bytes]:
        """Extract ASN as list of 4-byte packed values for capability encoding."""
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

    def to_int(self) -> int:
        """Return the ASN as a plain int."""
        return int(self)

    @classmethod
    def from_int(cls: Type[ASN], value: int) -> ASN:
        """Create an ASN from any int-like value. Returns ASN4 if value > 16-bit max."""
        # Avoid circular import
        from exabgp.bgp.message.open.capability.asn4 import ASN4

        if value > cls.MAX_2BYTE:
            return ASN4(value)
        return ASN(value)

    @classmethod
    def validate(cls: Type[ASN], value: int) -> bool:
        """Validate value is within 16-bit ASN range.

        Args:
            value: Integer ASN value

        Returns:
            True if valid, False otherwise
        """
        return 0 <= value <= cls.MAX_2BYTE


AS_TRANS = ASN(23456)
