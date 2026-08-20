"""asn.py

Created by Thomas Mangin on 2010-01-15.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from exabgp.util.types import Buffer
from struct import pack, unpack
from typing import Type, TypeVar

from exabgp.protocol.resource import Resource

_ASN = TypeVar('_ASN', bound='ASN')


def _decimal(value: str) -> bool:
    """True if the string is a plain ASCII decimal number (no sign, no separator).

    int() is too lenient to validate an ASN, so it must be gated on the text first:

        value          _decimal   int(value)
        '65001'        True       65001
        '0'            True       0
        '4294967295'   True       4294967295
        '-1'           False      -1            sign accepted by int()
        '+5'           False      5             sign accepted by int()
        '65_000'       False      65000         PEP 515 separator
        ' 5'           False      5             whitespace stripped by int()
        '5 '           False      5             whitespace stripped by int()
        '0x10'         False      ValueError
        '1.5'          False      ValueError
        '\u0661\u0662'       False      12            arabic-indic digits
        '\u00b2'           False      ValueError    superscript, isdigit() says True
        ''             False      ValueError

    isdigit() alone is not enough: it is true for the digits of any script, so the
    ASCII check is what keeps the last two rows out.
    """
    return bool(value) and value.isascii() and value.isdigit()


# =================================================================== ASN


class ASN(Resource):
    MAX_2BYTE = pow(2, 16) - 1  # Maximum 16-bit ASN value
    MAX_4BYTE = pow(2, 32) - 1  # Maximum 32-bit ASN value

    # ASN encoding size constants
    SIZE_4BYTE = 4  # 4-byte ASN encoding size
    SIZE_2BYTE = 2  # 2-byte ASN encoding size

    DOTTED_PARTS = 2  # <high>.<low> notation has two components

    def asn4(self) -> bool:
        return self > self.MAX_2BYTE

    def pack_asn2(self) -> bytes:
        return pack('!H', self)

    def pack_asn4(self) -> bytes:
        return pack('!L', self)

    def pack_asn(self, asn4: bool) -> bytes:
        return pack('!L' if asn4 else '!H', self)

    @classmethod
    def unpack_asn(cls: Type[ASN], data: Buffer, klass: Type[_ASN]) -> _ASN:
        if len(data) == cls.SIZE_4BYTE:
            value = unpack('!L', data)[0]
        elif len(data) == cls.SIZE_2BYTE:
            value = unpack('!H', data)[0]
        else:
            raise ValueError(f'ASN data invalid size: need {cls.SIZE_2BYTE} or {cls.SIZE_4BYTE} bytes, got {len(data)}')
        return klass(value)

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
        """Parse an ASN from its plain or dotted textual representation.

        Accepts "65001" (0 to 4294967295) and "1.1" (two components, each 0 to 65535).
        Anything else - negative values, out of range values, a wrong number of
        dotted components, non-decimal digits - raises ValueError.
        """
        if '.' in value:
            parts = value.split('.')
            if len(parts) != cls.DOTTED_PARTS:
                raise ValueError(
                    f"'{value}' is not a valid ASN\n  Format: <number> or <high>.<low> (e.g., 65001 or 1.1)"
                )
            components = []
            for part in parts:
                if not _decimal(part):
                    raise ValueError(f"'{value}' is not a valid ASN\n  Format: <high>.<low> (e.g., 1.1)")
                number = int(part)
                if number > cls.MAX_2BYTE:
                    raise ValueError(f"'{value}' is not a valid ASN\n  Each part must be 0 to {cls.MAX_2BYTE}")
                components.append(number)
            return cls((components[0] << 16) + components[1])

        if not _decimal(value):
            raise ValueError(f"'{value}' is not a valid ASN\n  Format: <number> or <high>.<low> (e.g., 65001 or 1.1)")

        as_number = int(value)
        if as_number > cls.MAX_4BYTE:
            raise ValueError(f"'{value}' is not a valid ASN\n  Must be 0 to {cls.MAX_4BYTE}")
        return cls(as_number)

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
