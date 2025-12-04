"""sr/srgb.py

Created by Evelio Vila 2017-02-16
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
"""

from __future__ import annotations

import json
from struct import pack
from struct import unpack
from typing import ClassVar

from exabgp.bgp.message.update.attribute.sr.prefixsid import PrefixSid

# 0                   1                   2                   3
# 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
# |     Type      |          Length               |    Flags      |
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
# |     Flags     |
# +-+-+-+-+-+-+-+-+
#
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
# |         SRGB 1 (6 octets)                                     |
# |                               +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
# |                               |
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
# |         SRGB n (6 octets)                                     |
# |                               +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
# |                               |
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
# 3.3.  Originator SRGB TLV


@PrefixSid.register()
class SrGb:
    TLV: ClassVar[int] = 3
    # Length is the total length of the value portion of the TLV: 2 +
    # multiple of 6.
    LENGTH: ClassVar[int] = -1

    def __init__(self, packed: bytes) -> None:
        # Payload format: Flags(2) + N * (Base(3) + Range(3))
        # Minimum: 2 bytes (flags only), remainder must be divisible by 6
        if len(packed) < 2 or (len(packed) - 2) % 6 != 0:
            raise ValueError(f'Invalid SRGB payload size: {len(packed)} bytes (must be 2 + N*6)')
        self._packed: bytes = packed

    @classmethod
    def make_srgb(cls, srgbs: list[tuple[int, int]]) -> 'SrGb':
        """Factory method for semantic construction."""
        payload: bytes = pack('!H', 0)  # flags
        for b, r in srgbs:
            payload = payload + pack('!L', b)[1:] + pack('!L', r)[1:]
        return cls(payload)

    @property
    def srgbs(self) -> list[tuple[int, int]]:
        """List of (base, range) tuples unpacked from _packed."""
        result: list[tuple[int, int]] = []
        data = self._packed[2:]  # Skip flags
        while data:
            base: int = unpack('!L', bytes([0]) + data[:3])[0]
            srange: int = unpack('!L', bytes([0]) + data[3:6])[0]
            result.append((base, srange))
            data = data[6:]
        return result

    def __repr__(self) -> str:
        items: list[str] = []
        for base, srange in self.srgbs:
            items.append(f'( {base},{srange} )')
        joined: str = ', '.join(items)
        return f'[ {joined} ]'

    def pack_tlv(self) -> bytes:
        return pack('!B', self.TLV) + pack('!H', len(self._packed)) + self._packed

    @classmethod
    def unpack_attribute(cls, data: bytes, length: int) -> SrGb:
        # Validation happens in __init__
        return cls(data)

    def json(self, compact: bool | None = None) -> str:
        return f'"sr-srgbs": {json.dumps(self.srgbs)}'
