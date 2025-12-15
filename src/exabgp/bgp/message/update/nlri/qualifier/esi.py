"""esi.py

Created by Thomas Mangin on 2012-07-08.
Copyright (c) 2014-2017 Orange. All rights reserved.
Copyright (c) 2014-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from exabgp.util.types import Buffer

# NOTE: RFC 7432 defines ESI Types (0-5) in the first byte.
# Current implementation treats ESI as opaque 10-byte value.
# Future: parse ESI Type and validate type-specific formats.


# Ethernet Segment Identifier
class ESI:
    LENGTH = 10  # RFC 7432 - Ethernet Segment Identifier is always 10 bytes

    DEFAULT = bytes([0x00] * LENGTH)  # All zeros
    MAX = bytes([0xFF] * LENGTH)  # All ones

    def __init__(self, packed: Buffer) -> None:
        if len(packed) != self.LENGTH:
            raise ValueError(f'ESI requires exactly {self.LENGTH} bytes, got {len(packed)}')
        self._packed = packed

    @classmethod
    def make_esi(cls, esi_bytes: Buffer) -> 'ESI':
        """Create ESI from bytes."""
        return cls(esi_bytes)

    @classmethod
    def make_default(cls) -> 'ESI':
        """Create ESI with default value (all zeros)."""
        return cls(cls.DEFAULT)

    @property
    def esi(self) -> Buffer:
        return self._packed

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ESI):
            return False
        return self._packed == other._packed

    def __lt__(self, other: object) -> bool:
        raise RuntimeError('comparing ESI for ordering does not make sense')

    def __le__(self, other: object) -> bool:
        raise RuntimeError('comparing ESI for ordering does not make sense')

    def __gt__(self, other: object) -> bool:
        raise RuntimeError('comparing ESI for ordering does not make sense')

    def __ge__(self, other: object) -> bool:
        raise RuntimeError('comparing ESI for ordering does not make sense')

    def __str__(self) -> str:
        if self._packed == self.DEFAULT:
            return '-'
        return ':'.join('{:02x}'.format(_) for _ in self._packed)

    def __repr__(self) -> str:
        return self.__str__()

    def pack_esi(self) -> Buffer:
        return self._packed

    def __len__(self) -> int:
        return self.LENGTH

    def __hash__(self) -> int:
        return hash(self._packed)

    @classmethod
    def unpack_esi(cls, data: Buffer) -> 'ESI':
        return cls(data[: cls.LENGTH])

    def json(self, compact: bool = False) -> str:
        return '"esi": "{}"'.format(str(self))
