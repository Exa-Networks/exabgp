# encoding: utf-8
"""
sr/srgb.py

Created by Evelio Vila 2017-02-16
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
"""

from __future__ import annotations

import json
from struct import pack
from struct import unpack

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
class SrGb(object):
    TLV = 3
    # Length is the total length of the value portion of the TLV: 2 +
    # multiple of 6.
    LENGTH = -1

    def __init__(self, srgbs, packed=None):
        self.srgbs = srgbs
        self.packed = self.pack()

    def __repr__(self):
        items = []
        for base, srange in self.srgbs:
            items.append(f'( {base},{srange} )')
        joined = ', '.join(items)
        return f'[ {joined} ]'

    def pack(self):
        payload = pack('!H', 0)  # flags
        for b, r in self.srgbs:
            payload = payload + pack('!L', b)[1:] + pack('!L', r)[1:]
        return pack('!B', self.TLV) + pack('!H', len(payload)) + payload

    @classmethod
    def unpack(cls, data, length):
        srgbs = []
        # Flags: 16 bits of flags.  None is defined by this document.  The
        # flag field MUST be clear on transmission and MUST be ignored at
        # reception.
        data = data[2:]
        # SRGB: 3 octets of base followed by 3 octets of range.  Note that
        # the SRGB field MAY appear multiple times.  If the SRGB field
        # appears multiple times, the SRGB consists of multiple ranges.
        while data:
            base = unpack('!L', bytes([0]) + data[:3])[0]
            srange = unpack('!L', bytes([0]) + data[3:6])[0]
            srgbs.append((base, srange))
            data = data[6:]
        return cls(srgbs=srgbs)

    def json(self, compact=None):
        return f'"sr-srgbs": {json.dumps(self.srgbs)}'
