"""etag.py

Created by Thomas Mangin on 2014-06-26.
Copyright (c) 2014-2017 Orange. All rights reserved.
Copyright (c) 2014-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

# TODO: take into account E-VPN specs that specify the role of the first bit of ESI
# (since draft-ietf-l2vpn-evpn-05)

from __future__ import annotations

from struct import pack, unpack

from exabgp.util.types import Buffer


class EthernetTag:
    MAX = pow(2, 32) - 1
    LENGTH = 4

    def __init__(self, packed: Buffer) -> None:
        if len(packed) != self.LENGTH:
            raise ValueError(f'EthernetTag requires exactly {self.LENGTH} bytes, got {len(packed)}')
        self._packed = packed

    @classmethod
    def make_etag(cls, tag: int) -> 'EthernetTag':
        """Create EthernetTag from integer value."""
        return cls(pack('!L', tag))

    @property
    def tag(self) -> int:
        value: int = unpack('!L', self._packed)[0]
        return value

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, EthernetTag):
            return False
        return self._packed == other._packed

    def __lt__(self, other: object) -> bool:
        raise RuntimeError('comparing EthernetTag for ordering does not make sense')

    def __le__(self, other: object) -> bool:
        raise RuntimeError('comparing EthernetTag for ordering does not make sense')

    def __gt__(self, other: object) -> bool:
        raise RuntimeError('comparing EthernetTag for ordering does not make sense')

    def __ge__(self, other: object) -> bool:
        raise RuntimeError('comparing EthernetTag for ordering does not make sense')

    def __str__(self) -> str:
        return repr(self.tag)

    def __repr__(self) -> str:
        return repr(self.tag)

    def pack_etag(self) -> Buffer:
        return self._packed

    def __len__(self) -> int:
        return self.LENGTH

    def __hash__(self) -> int:
        return hash(self._packed)

    @classmethod
    def unpack_etag(cls, data: Buffer) -> 'EthernetTag':
        return cls(data[: cls.LENGTH])

    def json(self, compact: bool = False) -> str:
        return '"ethernet-tag": {}'.format(self.tag)
