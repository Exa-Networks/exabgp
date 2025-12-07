"""bgp.py

Created by Thomas Mangin on 2012-07-08.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from struct import pack, unpack
from typing import ClassVar

from exabgp.util import hexstring
from exabgp.util.types import Buffer

# =========================================================== RouteDistinguisher
# RFC 4364


class RouteDistinguisher:
    NORD: ClassVar['RouteDistinguisher']

    # RFC 4364 - Route Distinguisher Type Field
    TYPE_AS2_ADMIN = 0  # Type 0: 2-byte AS administrator + 4-byte assigned number
    TYPE_IPV4_ADMIN = 1  # Type 1: IPv4 address administrator + 2-byte assigned number
    TYPE_AS4_ADMIN = 2  # Type 2: 4-byte AS administrator + 2-byte assigned number
    LENGTH = 8  # Route Distinguisher is always 8 bytes

    def __init__(self, packed: Buffer) -> None:
        # Allow empty bytes for NORD singleton
        if packed and len(packed) != self.LENGTH:
            raise ValueError(f'RouteDistinguisher requires exactly {self.LENGTH} bytes, got {len(packed)}')
        self._packed = packed

    @property
    def rd(self) -> Buffer:
        """Backward compatibility property."""
        return self._packed

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, RouteDistinguisher):
            return False
        return self._packed == other._packed

    def __lt__(self, other: object) -> bool:
        raise RuntimeError('comparing RouteDistinguisher for ordering does not make sense')

    def __le__(self, other: object) -> bool:
        raise RuntimeError('comparing RouteDistinguisher for ordering does not make sense')

    def __gt__(self, other: object) -> bool:
        raise RuntimeError('comparing RouteDistinguisher for ordering does not make sense')

    def __ge__(self, other: object) -> bool:
        raise RuntimeError('comparing RouteDistinguisher for ordering does not make sense')

    def pack_rd(self) -> Buffer:
        return self._packed

    def __len__(self) -> int:
        return len(self._packed)

    def _str(self) -> str:
        t, c1, c2, c3 = unpack('!HHHH', self._packed)
        if t == self.TYPE_AS2_ADMIN:
            rd = '%d:%d' % (c1, (c2 << 16) + c3)
        elif t == self.TYPE_IPV4_ADMIN:
            rd = '%d.%d.%d.%d:%d' % (c1 >> 8, c1 & 0xFF, c2 >> 8, c2 & 0xFF, c3)
        elif t == self.TYPE_AS4_ADMIN:
            rd = '%d:%d' % ((c1 << 16) + c2, c3)
        else:
            rd = hexstring(self._packed)
        return rd

    def json(self) -> str:
        if not self._packed:
            return ''
        return '"rd": "{}"'.format(self._str())

    def __hash__(self) -> int:
        return hash(self._packed)

    def __repr__(self) -> str:
        if not self._packed:
            return ''
        return ' rd {}'.format(self._str())

    @classmethod
    def unpack_routedistinguisher(cls, data: Buffer) -> 'RouteDistinguisher':
        return cls(data[: cls.LENGTH])

    @classmethod
    def make_from_elements(cls, prefix: str, suffix: int) -> 'RouteDistinguisher':
        """Create RouteDistinguisher from prefix:suffix notation."""
        try:
            if '.' in prefix:
                data = [bytes([0, 1])]
                data.extend([bytes([int(_)]) for _ in prefix.split('.')])
                data.extend([bytes([suffix >> 8]), bytes([suffix & 0xFF])])
                distinguisher = b''.join(data)
            else:
                number = int(prefix)
                if number < pow(2, 16) and suffix < pow(2, 32):
                    distinguisher = bytes([0, 0]) + pack('!H', number) + pack('!L', suffix)
                elif number < pow(2, 32) and suffix < pow(2, 16):
                    distinguisher = bytes([0, 2]) + pack('!L', number) + pack('!H', suffix)
                else:
                    raise ValueError('invalid route-distinguisher {}'.format(number))

            return cls(distinguisher)
        except ValueError:
            raise ValueError('invalid route-distinguisher {}:{}'.format(prefix, suffix)) from None


RouteDistinguisher.NORD = RouteDistinguisher(b'')
