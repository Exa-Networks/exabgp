"""cidr.py

Created by Thomas Mangin on 2013-08-07.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations
from typing import ClassVar, TYPE_CHECKING

if TYPE_CHECKING:
    from exabgp.bgp.message.open.capability.negotiated import Negotiated

import math

from exabgp.protocol.family import AFI
from exabgp.protocol.ip import IP
from exabgp.bgp.message.notification import Notify

# CIDR netmask constants
CIDR_IPV4_MAX_MASK = 24  # Maximum IPv4 mask for heuristic detection
CIDR_IPV6_LENGTH_BYTES = 4  # IPv6 address length in bytes (for detection)


class CIDR:
    EOR: bool = False

    _mask_to_bytes: dict[int, int] = {}

    NOCIDR: ClassVar[CIDR]

    def __init__(self, packed: bytes, mask: int) -> None:
        self._packed = packed
        self.mask = mask
        self._ip: str | None = None

    @classmethod
    def size(cls, mask: int) -> int:
        return cls._mask_to_bytes.get(mask, 0)

    # have a .raw for the ip
    # have a .mask for the mask
    # have a .bgp with the bgp wire format of the prefix

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, CIDR):
            return NotImplemented
        return self.mask == other.mask and self._packed == other._packed

    def __ne__(self, other: object) -> bool:
        if not isinstance(other, CIDR):
            return NotImplemented
        return self.mask != other.mask or self._packed != other._packed

    def __lt__(self, other: CIDR) -> bool:
        return self._packed < other._packed

    def __le__(self, other: CIDR) -> bool:
        return self._packed <= other._packed

    def __gt__(self, other: CIDR) -> bool:
        return self._packed > other._packed

    def __ge__(self, other: CIDR) -> bool:
        return self._packed >= other._packed

    def top(self, negotiated: Negotiated | None = None, afi: AFI = AFI.undefined) -> str:
        if not self._ip:
            self._ip = IP.ntop(self._packed)
        return self._ip

    def ton(self, negotiated: Negotiated | None = None, afi: AFI = AFI.undefined) -> bytes:
        return self._packed

    def __repr__(self) -> str:
        return self.prefix()

    def prefix(self) -> str:
        return '{}/{}'.format(self.top(), self.mask)

    def index(self) -> str:
        return str(self.mask) + str(self._packed[: CIDR.size(self.mask)])

    def pack_ip(self) -> bytes:
        return bytes(self._packed[: CIDR.size(self.mask)])

    def pack_nlri(self) -> bytes:
        return bytes([self.mask]) + bytes(self._packed[: CIDR.size(self.mask)])

    @staticmethod
    def decode(afi: AFI, bgp: bytes) -> tuple[bytes, int]:
        mask = bgp[0]
        size = CIDR.size(mask)

        if len(bgp) < size + 1:
            raise Notify(3, 10, 'could not decode CIDR')

        return bgp[1 : size + 1] + bytes(IP.length(afi) - size), mask

        # data = bgp[1:size+1] + '\x0\x0\x0\x0'
        # return data[:4], mask

    @classmethod
    def unpack_cidr(cls, data: bytes) -> CIDR:
        afi = AFI.ipv6 if len(data) > CIDR_IPV6_LENGTH_BYTES or data[0] > CIDR_IPV4_MAX_MASK else AFI.ipv4
        prefix, mask = cls.decode(afi, data)
        return cls(prefix, mask)

    def __len__(self) -> int:
        return CIDR.size(self.mask) + 1

    def __hash__(self) -> int:
        return hash(bytes([self.mask]) + self._packed)


for netmask in range(129):
    CIDR._mask_to_bytes[netmask] = int(math.ceil(float(netmask) / 8))

CIDR.NOCIDR = CIDR(b'', 0)
