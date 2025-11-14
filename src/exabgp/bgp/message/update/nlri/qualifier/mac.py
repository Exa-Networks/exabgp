"""mac.py

Created by Thomas Mangin on 2012-07-08.
Copyright (c) 2014-2017 Orange. All rights reserved.
Copyright (c) 2014-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations
from typing import Any, Optional, Type


# ========================================================================== MAC
#


class MAC:
    def __init__(self, mac: Optional[str] = None, packed: Optional[bytes] = None) -> None:
        self.mac: Optional[str] = mac
        self._packed: bytes = packed if packed else b''.join(bytes([int(_, 16)]) for _ in mac.split(':'))  # type: ignore[union-attr]

    def __eq__(self, other: object) -> bool:
        # Compare packed representation to handle case-insensitive MAC addresses
        if not isinstance(other, MAC):
            return False
        return self._packed == other._packed

    def __neq__(self, other: object) -> bool:
        if not isinstance(other, MAC):
            return True
        return self.mac != other.mac

    def __lt__(self, other: object) -> bool:
        raise RuntimeError('comparing MAC for ordering does not make sense')

    def __le__(self, other: object) -> bool:
        raise RuntimeError('comparing MAC for ordering does not make sense')

    def __gt__(self, other: object) -> bool:
        raise RuntimeError('comparing MAC for ordering does not make sense')

    def __ge__(self, other: object) -> bool:
        raise RuntimeError('comparing MAC for ordering does not make sense')

    def __str__(self) -> str:
        return ':'.join('{:02X}'.format(_) for _ in self._packed)

    def __repr__(self) -> str:
        return self.__str__()

    def pack(self) -> bytes:
        return self._packed

    # Orange code was returning 10 !
    def __len__(self) -> int:
        return 6

    # XXX: FIXME: improve for better performance ?
    def __hash__(self) -> int:
        return hash(str(self))

    @classmethod
    def unpack(cls: Type[MAC], data: bytes) -> MAC:
        return cls(':'.join('{:02X}'.format(_) for _ in data[:6]), data[:6])

    def json(self, compact: Any = None) -> str:
        return '"mac": "{}"'.format(str(self))
