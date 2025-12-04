"""sradj.py

Created by Evelio Vila
Copyright (c) 2014-2017 Exa Networks. All rights reserved.
"""

from __future__ import annotations

import json
from struct import unpack
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
class SrAdjacency(FlagLS):
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
    def unpack_bgpls(cls, data: bytes) -> SrAdjacency:
        if len(data) < SRADJ_MIN_LENGTH:
            raise Notify(3, 5, f'SR Adjacency SID: data too short, need {SRADJ_MIN_LENGTH} bytes, got {len(data)}')
        return cls(data)

    def json(self, compact: bool = False) -> str:
        return '"sr-adj": ' + json.dumps(
            {
                'flags': self.flags,
                'sids': self.sids,
                'weight': self.weight,
                'undecoded-sids': self.undecoded,
            },
        )
