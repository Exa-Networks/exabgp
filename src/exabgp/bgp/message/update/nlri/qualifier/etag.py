"""etag.py

Created by Thomas Mangin on 2014-06-26.
Copyright (c) 2014-2017 Orange. All rights reserved.
Copyright (c) 2014-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

# TODO: take into account E-VPN specs that specify the role of the first bit of ESI
# (since draft-ietf-l2vpn-evpn-05)

from __future__ import annotations
from typing import Type

from struct import pack
from struct import unpack


class EthernetTag:
    MAX = pow(2, 32) - 1

    def __init__(self, tag: int = 0) -> None:
        self.tag: int = tag

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, EthernetTag):
            return False
        return self.tag == other.tag

    def __neq__(self, other: object) -> bool:
        if not isinstance(other, EthernetTag):
            return True
        return self.tag != other.tag

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

    def pack_etag(self) -> bytes:
        return pack('!L', self.tag)

    def __len__(self) -> int:
        return 4

    def __hash__(self) -> int:
        return hash(self.tag)

    @classmethod
    def unpack_etag(cls: Type[EthernetTag], data: bytes) -> EthernetTag:
        return cls(unpack('!L', data[:4])[0])

    def json(self, compact: bool = False) -> str:
        return '"ethernet-tag": {}'.format(self.tag)
