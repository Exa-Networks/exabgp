"""esi.py

Created by Thomas Mangin on 2012-07-08.
Copyright (c) 2014-2017 Orange. All rights reserved.
Copyright (c) 2014-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations
from typing import Optional, Type

# TODO: take into account E-VPN specs that specify the role of the first bit of ESI
# (since draft-ietf-l2vpn-evpn-05)


# Ethernet Segment Identifier
class ESI:
    LENGTH = 10  # RFC 7432 - Ethernet Segment Identifier is always 10 bytes

    DEFAULT = bytes([0x00] * LENGTH)  # All zeros
    MAX = bytes([0xFF] * LENGTH)  # All ones

    def __init__(self, esi: Optional[bytes] = None) -> None:
        self.esi: bytes = self.DEFAULT if esi is None else esi
        if len(self.esi) != self.LENGTH:
            raise Exception(f'incorrect ESI, len {len(esi)} instead of {self.LENGTH}')  # type: ignore[arg-type]

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ESI):
            return False
        return self.esi == other.esi

    def __neq__(self, other: object) -> bool:
        if not isinstance(other, ESI):
            return True
        return self.esi != other.esi

    def __lt__(self, other: object) -> bool:
        raise RuntimeError('comparing ESI for ordering does not make sense')

    def __le__(self, other: object) -> bool:
        raise RuntimeError('comparing ESI for ordering does not make sense')

    def __gt__(self, other: object) -> bool:
        raise RuntimeError('comparing ESI for ordering does not make sense')

    def __ge__(self, other: object) -> bool:
        raise RuntimeError('comparing ESI for ordering does not make sense')

    def __str__(self) -> str:
        if self.esi == self.DEFAULT:
            return '-'
        return ':'.join('{:02x}'.format(_) for _ in self.esi)

    def __repr__(self) -> str:
        return self.__str__()

    def pack_esi(self) -> bytes:
        return self.esi

    def __len__(self) -> int:
        return self.LENGTH

    def __hash__(self) -> int:
        return hash(self.esi)

    @classmethod
    def unpack_esi(cls: Type[ESI], data: bytes) -> ESI:
        return cls(data[: cls.LENGTH])

    def json(self, compact: bool = False) -> str:
        return '"esi": "{}"'.format(str(self))
