"""srprefix.py

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

#    draft-gredler-idr-bgp-ls-segment-routing-ext-03
#    0                   1                   2                   3
#    0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
#   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#   |               Type            |            Length             |
#   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#   |     Flags       |  Algorithm  |           Reserved            |
#   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#   |                       SID/Index/Label (variable)              |
#   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+

# 	draft-ietf-isis-segment-routing-extensions Prefix-SID Sub-TLV

# SID/Label data length when flags are not set
SID_LABEL_LENGTH_NO_FLAGS = 4  # Length of SID/Label when V and L flags are both false

# Minimum data length for SR Prefix SID TLV
# Flags (1) + Algorithm (1) + Reserved (2) = 4 bytes
SRPREFIX_MIN_LENGTH = 4


@LinkState.register_lsid()
class PrefixSid(FlagLS):
    TLV = 1158
    FLAGS = ['R', 'N', 'P', 'E', 'V', 'L', 'RSV', 'RSV']

    # flags property is inherited from FlagLS and unpacks from _packed[0:1]

    @property
    def sr_algo(self) -> int:
        """Unpack and return the SR algorithm from packed bytes."""
        return self._packed[1]

    @property
    def sids(self) -> list[int]:
        """Unpack and return the SIDs from packed bytes."""
        flags = self.flags
        data = self._packed[4:]  # Skip Flags(1) + Algorithm(1) + Reserved(2)
        sids = []
        while data:
            if flags['V'] and flags['L']:
                sid = unpack('!L', bytes([0]) + data[:3])[0]
                data = data[3:]
                sids.append(sid)
            elif (not flags['V']) and (not flags['L']):
                if len(data) < SID_LABEL_LENGTH_NO_FLAGS:
                    break
                sid = unpack('!I', data[:SID_LABEL_LENGTH_NO_FLAGS])[0]
                data = data[SID_LABEL_LENGTH_NO_FLAGS:]
                sids.append(sid)
            else:
                break
        return sids

    @property
    def undecoded(self) -> tuple[str, ...]:
        """Unpack and return any undecoded SID data from packed bytes."""
        flags = self.flags
        data = self._packed[4:]  # Skip Flags(1) + Algorithm(1) + Reserved(2)
        raw = []
        while data:
            if flags['V'] and flags['L']:
                data = data[3:]
            elif (not flags['V']) and (not flags['L']):
                if len(data) < SID_LABEL_LENGTH_NO_FLAGS:
                    raw.append(hexstring(data))
                    break
                data = data[SID_LABEL_LENGTH_NO_FLAGS:]
            else:
                raw.append(hexstring(data))
                break
        return tuple(raw)

    def __repr__(self) -> str:
        return 'prefix_flags: {}, sids: {}, undecoded_sid: {}'.format(self.flags, self.sids, self.undecoded)

    @classmethod
    def unpack_bgpls(cls, data: bytes) -> PrefixSid:
        if len(data) < SRPREFIX_MIN_LENGTH:
            raise Notify(3, 5, f'SR Prefix SID: data too short, need {SRPREFIX_MIN_LENGTH} bytes, got {len(data)}')
        # Validation for V/L flags and SID length
        flags = cls.unpack_flags(data[0:1])
        sid_data = data[4:]
        if (not flags['V']) and (not flags['L']) and len(sid_data) != SID_LABEL_LENGTH_NO_FLAGS:
            raise Notify(3, 5, "SID/Label size doesn't match V and L flag state")
        return cls(data)

    def json(self, compact: bool = False) -> str:
        return f'"sr-prefix-flags": {json.dumps(self.flags)}, "sids": {json.dumps(self.sids)}, "undecoded-sids": {json.dumps(self.undecoded)}, "sr-algorithm": {json.dumps(self.sr_algo)}'

    @classmethod
    def make_prefix_sid(cls, flags: dict[str, int], sids: list[int], sr_algo: int) -> PrefixSid:
        """Create PrefixSid from semantic values.

        Args:
            flags: Dict with R, N, P, E, V, L flag values (0 or 1)
            sids: List of SID/Label values
            sr_algo: SR algorithm value

        Returns:
            PrefixSid instance with packed wire-format bytes
        """
        flags_byte = (
            (flags.get('R', 0) << 7)
            | (flags.get('N', 0) << 6)
            | (flags.get('P', 0) << 5)
            | (flags.get('E', 0) << 4)
            | (flags.get('V', 0) << 3)
            | (flags.get('L', 0) << 2)
        )
        # Flags (1) + Algorithm (1) + Reserved (2)
        packed = pack('!BBH', flags_byte, sr_algo, 0)
        # Add SIDs based on V/L flags
        if flags.get('V', 0) and flags.get('L', 0):
            # 3-byte label
            for sid in sids:
                packed += pack('!I', sid)[1:]  # Take last 3 bytes
        else:
            # 4-byte index
            for sid in sids:
                packed += pack('!I', sid)
        return cls(packed)
