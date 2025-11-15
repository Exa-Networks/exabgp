"""sr/srgb.py

Created by Evelio Vila 2017-02-16
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
"""

from __future__ import annotations

import json
from struct import pack
from struct import unpack
from typing import ClassVar, List, Optional, Tuple

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

    def __init__(self, srgbs: List[Tuple[int, int]], packed: Optional[bytes] = None) -> None:
        self.srgbs: List[Tuple[int, int]] = srgbs
        self.packed: bytes = self.pack_tlv()

    def __repr__(self) -> str:
        items: List[str] = []
        for base, srange in self.srgbs:
            items.append(f'( {base},{srange} )')
        joined: str = ', '.join(items)
        return f'[ {joined} ]'

    def pack_tlv(self) -> bytes:
        payload: bytes = pack('!H', 0)  # flags
        for b, r in self.srgbs:
            payload = payload + pack('!L', b)[1:] + pack('!L', r)[1:]
        return pack('!B', self.TLV) + pack('!H', len(payload)) + payload

    @classmethod
    def unpack_attribute(cls, data: bytes, length: int) -> SrGb:
        srgbs: List[Tuple[int, int]] = []
        # Flags: 16 bits of flags.  None is defined by this document.  The
        # flag field MUST be clear on transmission and MUST be ignored at
        # reception.
        data = data[2:]
        # SRGB: 3 octets of base followed by 3 octets of range.  Note that
        # the SRGB field MAY appear multiple times.  If the SRGB field
        # appears multiple times, the SRGB consists of multiple ranges.
        while data:
            base: int = unpack('!L', bytes([0]) + data[:3])[0]
            srange: int = unpack('!L', bytes([0]) + data[3:6])[0]
            srgbs.append((base, srange))
            data = data[6:]
        return cls(srgbs=srgbs)

    def json(self, compact: Optional[bool] = None) -> str:
        return f'"sr-srgbs": {json.dumps(self.srgbs)}'
