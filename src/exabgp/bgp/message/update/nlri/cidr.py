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

# Valid IP address lengths
CIDR_IPV4_LENGTH = 4
CIDR_IPV6_LENGTH = 16
CIDR_MAX_MASK = 128


class CIDR:
    EOR: bool = False

    _mask_to_bytes: dict[int, int] = {}

    NOCIDR: ClassVar['CIDR']

    def __init__(self, nlri: bytes, afi: AFI) -> None:
        """Create a CIDR from NLRI wire format bytes.

        Args:
            nlri: NLRI wire format bytes [mask][truncated_ip...]
            afi: Address family (ipv4 or ipv6) - required for correct padding

        Raises:
            Notify: If NLRI data is too short for the mask
        """
        prefix, mask = self.decode(afi, nlri)
        self._packed = prefix
        self._mask = mask

    @classmethod
    def _create_nocidr(cls) -> 'CIDR':
        """Create the NOCIDR singleton. Called once at module load."""
        instance = object.__new__(cls)
        instance._packed = b''
        instance._mask = 0
        return instance

    @classmethod
    def make_cidr(cls, packed: bytes, mask: int) -> 'CIDR':
        """Factory method to create a CIDR from packed IP bytes and mask.

        Args:
            packed: Full IP address bytes (4 bytes for IPv4, 16 for IPv6)
            mask: Prefix length

        Returns:
            New CIDR instance

        Raises:
            ValueError: If packed length is invalid or mask is out of range
        """
        if packed:
            if len(packed) not in (CIDR_IPV4_LENGTH, CIDR_IPV6_LENGTH):
                raise ValueError(
                    f'CIDR packed must be {CIDR_IPV4_LENGTH} or {CIDR_IPV6_LENGTH} bytes, got {len(packed)}'
                )
            max_mask = 32 if len(packed) == CIDR_IPV4_LENGTH else CIDR_MAX_MASK
            if not (0 <= mask <= max_mask):
                raise ValueError(f'CIDR mask must be 0-{max_mask}, got {mask}')
        instance = object.__new__(cls)
        instance._packed = packed
        instance._mask = mask
        return instance

    @property
    def mask(self) -> int:
        """Prefix length (0-32 for IPv4, 0-128 for IPv6)."""
        return self._mask

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
        """Return the IP address as a string."""
        return IP.ntop(self._packed)

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
        # Infer AFI from wire format using heuristic: IPv6 if mask > 32 or data too long for IPv4
        afi = AFI.ipv6 if len(data) > CIDR_IPV6_LENGTH_BYTES or data[0] > CIDR_IPV4_MAX_MASK else AFI.ipv4
        return cls(data, afi)

    def __len__(self) -> int:
        return CIDR.size(self.mask) + 1

    def __hash__(self) -> int:
        return hash(bytes([self.mask]) + self._packed)


for netmask in range(129):
    CIDR._mask_to_bytes[netmask] = int(math.ceil(float(netmask) / 8))

CIDR.NOCIDR = CIDR._create_nocidr()
