"""sradj.py

Created by Evelio Vila
Copyright (c) 2014-2017 Exa Networks. All rights reserved.
"""

from __future__ import annotations

import json
from struct import pack, unpack
from exabgp.util import hexstring

from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.update.attribute.bgpls.linkstate import LinkState
from exabgp.bgp.message.update.attribute.bgpls.linkstate import FlagLS

# Minimum data length for SR Adjacency SID TLV
# Flags (1) + Weight (1) + Reserved (2) = 4 bytes
SRADJ_MIN_LENGTH = 4

#    draft-gredler-idr-bgp-ls-segment-routing-ext-03
#    0                   1                   2                   3
#    0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
#   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#   |               Type            |              Length           |
#   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#   | Flags         |     Weight    |             Reserved          |
#   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#   |                   SID/Label/Index (variable)                  |
#   +---------------------------------------------------------------+
#


@LinkState.register_lsid()
class AdjacencySid(FlagLS):
    TLV = 1099
    FLAGS = ['F', 'B', 'V', 'L', 'S', 'P', 'RSV', 'RSV']

    # flags property is inherited from FlagLS and unpacks from _packed[0:1]

    @property
    def weight(self) -> int:
        """Unpack and return the weight from packed bytes."""
        return self._packed[1]

    @property
    def sids(self) -> list[int]:
        """Unpack and return the SIDs from packed bytes."""
        flags = self.flags
        data = self._packed[4:]  # Skip Flags(1) + Weight(1) + Reserved(2)
        sids = []
        while data:
            if int(flags['V']) and int(flags['L']):
                sid = unpack('!L', bytes([0]) + data[:3])[0]
                data = data[3:]
                sids.append(sid)
            elif (not flags['V']) and (not flags['L']):
                sid = unpack('!I', data[:4])[0]
                data = data[4:]
                sids.append(sid)
            else:
                break
        return sids

    @property
    def undecoded(self) -> tuple[str, ...]:
        """Unpack and return any undecoded SID data from packed bytes."""
        flags = self.flags
        data = self._packed[4:]  # Skip Flags(1) + Weight(1) + Reserved(2)
        raw = []
        while data:
            if int(flags['V']) and int(flags['L']):
                data = data[3:]
            elif (not flags['V']) and (not flags['L']):
                data = data[4:]
            else:
                raw.append(hexstring(data))
                break
        return tuple(raw)

    def __repr__(self) -> str:
        return 'adj_flags: {}, sids: {}, undecoded_sid {}'.format(self.flags, self.sids, self.undecoded)

    @classmethod
    def unpack_bgpls(cls, data: bytes) -> AdjacencySid:
        if len(data) < SRADJ_MIN_LENGTH:
            raise Notify(3, 5, f'SR Adjacency SID: data too short, need {SRADJ_MIN_LENGTH} bytes, got {len(data)}')
        return cls(data)

    @classmethod
    def make_adjacencysid(
        cls,
        flags: dict[str, int],
        weight: int,
        sids: list[int],
    ) -> AdjacencySid:
        """Create AdjacencySid from semantic values.

        Args:
            flags: Dict with keys F, B, V, L, S, P (RSV bits ignored)
            weight: Weight value (0-255)
            sids: List of SID values

        Returns:
            AdjacencySid instance with packed wire-format bytes
        """
        # Pack flags byte: F(7), B(6), V(5), L(4), S(3), P(2), RSV(1), RSV(0)
        flags_byte = (
            (flags.get('F', 0) << 7)
            | (flags.get('B', 0) << 6)
            | (flags.get('V', 0) << 5)
            | (flags.get('L', 0) << 4)
            | (flags.get('S', 0) << 3)
            | (flags.get('P', 0) << 2)
        )

        # Pack header: Flags(1) + Weight(1) + Reserved(2)
        packed = pack('!BBH', flags_byte, weight, 0)

        # Pack SIDs based on V and L flags
        v_flag = flags.get('V', 0)
        l_flag = flags.get('L', 0)
        for sid in sids:
            if v_flag and l_flag:
                # 3-byte label: 20-bit label value in upper bits
                packed += pack('!L', sid << 4)[1:]  # Take last 3 bytes
            else:
                # 4-byte index
                packed += pack('!I', sid)

        return cls(packed)

    def json(self, compact: bool = False) -> str:
        return '"sr-adj": ' + json.dumps(
            {
                'flags': self.flags,
                'sids': self.sids,
                'weight': self.weight,
                'undecoded-sids': self.undecoded,
            },
        )
