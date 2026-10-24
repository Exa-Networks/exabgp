"""sr/srgb.py

Created by Evelio Vila 2017-02-16
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
"""

from __future__ import annotations

import json
from struct import pack
from struct import unpack

from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.update.attribute.sr.prefixsid import PrefixSid

# RFC 8669 3.2: two octets of flags, then one or more ranges of three octets of base
# followed by three octets of range.  Named so the check in unpack and the walk it guards
# read the same sizes and cannot drift apart.
SRGB_FLAGS_SIZE = 2
SRGB_RANGE_SIZE = 6

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
        # the walk below reads six octets at a time and used to trust the peer for the
        # count: a value which is not 2 + N*6 ran it off the end of the buffer and raised
        # struct.error, which is not a decoder result.  It left Update.unpack_message
        # untyped and came back to the peer from the catch-all in reactor/protocol.py as
        # Notify(1, 0), a Message Header Error for an attribute fault.  Peer bytes produce
        # a Notify, and Attributes.DISCARD then makes it cost the attribute.
        if length < SRGB_FLAGS_SIZE + SRGB_RANGE_SIZE or (length - SRGB_FLAGS_SIZE) % SRGB_RANGE_SIZE:
            raise Notify(3, 5, f'invalid originator SRGB TLV size, should be 2 + n*6 but {length} received')
        srgbs = []
        # Flags: 16 bits of flags.  None is defined by this document.  The
        # flag field MUST be clear on transmission and MUST be ignored at
        # reception.
        data = data[SRGB_FLAGS_SIZE:]
        # SRGB: 3 octets of base followed by 3 octets of range.  Note that
        # the SRGB field MAY appear multiple times.  If the SRGB field
        # appears multiple times, the SRGB consists of multiple ranges.
        while data:
            base = unpack('!L', bytes([0]) + data[:3])[0]
            srange = unpack('!L', bytes([0]) + data[3:6])[0]
            srgbs.append((base, srange))
            data = data[SRGB_RANGE_SIZE:]
        return cls(srgbs=srgbs)

    def json(self, compact=None):
        return f'"sr-srgbs": {json.dumps(self.srgbs)}'

    def as_dict(self):
        return {'sr-srgbs': self.srgbs}
