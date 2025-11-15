"""sradj.py

Created by Evelio Vila
Copyright (c) 2014-2017 Exa Networks. All rights reserved.
"""

from __future__ import annotations

import json
from struct import unpack
from exabgp.util import hexstring

from exabgp.bgp.message.update.attribute.bgpls.linkstate import LinkState
from exabgp.bgp.message.update.attribute.bgpls.linkstate import FlagLS

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


@LinkState.register()
class SrAdjacency(FlagLS):
    TLV = 1099
    FLAGS = ['F', 'B', 'V', 'L', 'S', 'P', 'RSV', 'RSV']

    def __init__(self, flags, sids, weight, undecoded=()):
        self.flags = flags
        self.sids = sids
        self.weight = weight
        self.undecoded = undecoded

    def __repr__(self):
        return 'adj_flags: {}, sids: {}, undecoded_sid {}'.format(self.flags, self.sids, self.undecoded)

    @classmethod
    def unpack_bgpls(cls, data: bytes) -> SrAdjacency:
        # We only support IS-IS flags for now.
        flags = cls.unpack_flags(data[0:1])
        # Parse adj weight
        weight = data[1]
        # Move pointer 4 bytes: Flags(1) + Weight(1) + Reserved(2)
        data = data[4:]
        # SID/Index/Label: according to the V and L flags, it contains
        # either:
        # *  A 3 octet local label where the 20 rightmost bits are used for
        # 	 encoding the label value.  In this case the V and L flags MUST
        # 	 be set.
        #
        # *  A 4 octet index defining the offset in the SID/Label space
        # 	 advertised by this router using the encodings defined in
        #  	 Section 3.1.  In this case V and L flags MUST be unset.
        sids = []
        raw = []
        while data:
            # Range Size: 3 octet value indicating the number of labels in
            # the range.
            if int(flags['V']) and int(flags['L']):
                sid = unpack('!L', bytes([0]) + data[:3])[0]
                data = data[3:]
                sids.append(sid)
            elif (not flags['V']) and (not flags['L']):
                sid = unpack('!I', data[:4])[0]
                data = data[4:]
                sids.append(sid)
            else:
                raw.append(hexstring(data))
                break

        return cls(flags=flags, sids=sids, weight=weight, undecoded=raw)

    def json(self, compact: bool = False):
        return '"sr-adj": ' + json.dumps(
            {
                'flags': self.flags,
                'sids': self.sids,
                'weight': self.weight,
                'undecoded-sids': self.undecoded,
            },
        )
