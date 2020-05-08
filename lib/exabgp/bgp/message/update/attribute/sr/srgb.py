# encoding: utf-8
"""
sr/srgb.py

Created by Evelio Vila 2017-02-16
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
"""
import json
from struct import pack

from exabgp.util import concat_bytes
from exabgp.vendoring.bitstring import BitArray
from exabgp.bgp.message.notification import Notify
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
            items.append("( {},{} )".format(base, srange))
        return '[ {} ]'.format(', '.join(items))

    def pack(self):
        payload = pack('!H', 0)  # flags
        for b, r in self.srgbs:
            payload = concat_bytes(payload, pack("!L", b)[1:], pack("!L", r)[1:])
        return concat_bytes(pack('!B', self.TLV), pack('!H', len(payload)), payload)

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
            b = BitArray(bytes=data[:3])
            base = b.unpack('uintbe:24')[0]
            b = BitArray(bytes=data[3:6])
            srange = b.unpack('uintbe:24')[0]
            srgbs.append((base, srange))
            data = data[6:]
        return cls(srgbs=srgbs)

    def json(self, compact=None):
        return '"sr-srgbs": {}'.format((json.dumps(self.srgbs)))
