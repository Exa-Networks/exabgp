# encoding: utf-8
"""
sradj.py

Created by Evelio Vila
Copyright (c) 2014-2017 Exa Networks. All rights reserved.
"""

import json
from struct import unpack
from exabgp.vendoring import six
from exabgp.util import hexstring

from exabgp.vendoring.bitstring import BitArray
from exabgp.bgp.message.update.attribute.bgpls.linkstate import LINKSTATE, LsGenericFlags

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


@LINKSTATE.register()
class SrAdjacency(object):
    TLV = 1099

    def __init__(self, flags, sids, weight, undecoded=[]):
        self.flags = flags
        self.sids = sids
        self.weight = weight
        self.undecoded = undecoded

    def __repr__(self):
        return "adj_flags: %s, sids: %s, undecoded_sid" % (self.flags, self.sids, self.undecoded)

    @classmethod
    def unpack(cls, data, length):
        # We only support IS-IS flags for now.
        flags = LsGenericFlags.unpack(data[0:1], LsGenericFlags.ISIS_SR_ADJ_FLAGS)
        # Parse adj weight
        weight = six.indexbytes(data, 1)
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
            if int(flags.flags['V']) and int(flags.flags['L']):
                b = BitArray(bytes=data[:3])
                sid = b.unpack('uintbe:24')[0:1]
                data = data[3:]
                sids.append(sid)
            elif (not flags.flags['V']) and (not flags.flags['L']):
                sid = unpack('!I', data[:4])[0:1]
                data = data[4:]
                sids.append(sid)
            else:
                raw.append(hexstring(data))
                break

        return cls(flags=flags, sids=sids, weight=weight, undecoded=raw)

    def json(self, compact=None):
        return ', '.join(
            [
                '"sr-adj-flags": {}'.format(self.flags.json()),
                '"sids": {}'.format(json.dumps(self.sids)),
                '"undecoded-sids": {}'.format(json.dumps(self.undecoded)),
                '"sr-adj-weight": {}'.format(json.dumps(self.weight)),
            ]
        )
