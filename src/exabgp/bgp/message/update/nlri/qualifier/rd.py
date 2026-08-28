"""bgp.py

Created by Thomas Mangin on 2012-07-08.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from copy import deepcopy

from struct import pack, unpack
from typing import Any, ClassVar

from exabgp.bgp.message.notification import Notify
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
        if len(data) != cls.LENGTH:
            raise Notify(3, 10, f'Route Distinguisher requires exactly {cls.LENGTH} bytes, got {len(data)}')
        return cls(data)

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

    def __copy__(self) -> 'RouteDistinguisher':
        """Preserve the NORD singleton across a copy.

        NORD is compared with `is` by callers, so a copy which is a different object
        makes a copied route stop recognising it.  Session 5.0 hit this on PathInfo.NOPATH,
        where the identity test sat inside index(), so a deep copied route indexed
        differently from the route it was copied from and the RIB lost it on withdraw.
        """
        if self is RouteDistinguisher.NORD:
            return self
        # type(self) and the whole __dict__, not RouteDistinguisher and _packed by name.  The default
        # copy carried everything this object held; naming one attribute means a second one
        # added later is silently dropped by a method nobody will think to revisit.
        new = type(self).__new__(type(self))
        new.__dict__.update(self.__dict__)
        return new

    def __deepcopy__(self, memo: dict[Any, Any]) -> 'RouteDistinguisher':
        """Preserve the NORD singleton across a deep copy.

        _packed is bytes and immutable, so there is nothing under it to copy.
        """
        if self is RouteDistinguisher.NORD:
            return self
        new = type(self).__new__(type(self))
        memo[id(self)] = new
        # deepcopy the values rather than sharing them: _packed is bytes and immutable
        # today, and a mutable attribute added later would otherwise be shared silently
        for attribute, value in self.__dict__.items():
            setattr(new, attribute, deepcopy(value, memo))
        return new


RouteDistinguisher.NORD = RouteDistinguisher(b'')
