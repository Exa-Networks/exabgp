"""mac.py

Created by Thomas Mangin on 2012-07-08.
Copyright (c) 2014-2017 Orange. All rights reserved.
Copyright (c) 2014-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from typing import Type

from exabgp.util.types import Buffer

# ========================================================================== MAC
#


class MAC:
    def __init__(self, mac: str | None = None, packed: Buffer | None = None) -> None:
        self.mac: str | None = mac
        if packed:
            self._packed: bytes = packed
        else:
            assert mac is not None, 'Either mac or packed must be provided'
            self._packed = b''.join(bytes([int(_, 16)]) for _ in mac.split(':'))

    def __eq__(self, other: object) -> bool:
        # Compare packed representation to handle case-insensitive MAC addresses
        if not isinstance(other, MAC):
            return False
        return self._packed == other._packed

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

    def pack_mac(self) -> Buffer:
        return self._packed

    # Orange code was returning 10 !
    def __len__(self) -> int:
        return 6

    def __hash__(self) -> int:
        # Using packed bytes is ~17x faster than hash(str(self))
        # See lab/benchmark_mac_hash.py for benchmark
        return hash(self._packed)

    @classmethod
    def unpack_mac(cls: Type[MAC], data: Buffer) -> MAC:
        return cls(':'.join('{:02X}'.format(_) for _ in data[:6]), data[:6])

    def json(self, compact: bool = False) -> str:
        return '"mac": "{}"'.format(str(self))
