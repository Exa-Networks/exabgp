# encoding: utf-8
"""
srcap.py

Created by Evelio Vila
Copyright (c) 2014-2017 Exa Networks. All rights reserved.
"""

import json
from struct import unpack

from exabgp.vendoring.bitstring import BitArray
from exabgp.bgp.message.update.attribute.bgpls.linkstate import LINKSTATE, LsGenericFlags
from exabgp.bgp.message.notification import Notify

#    draft-gredler-idr-bgp-ls-segment-routing-ext-03
#   0                   1                   2                   3
#    0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
#   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#   |               Type            |               Length          |
#   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#   |      Flags    |   RESERVED    |
#   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#
#   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#   |                  Range Size                   |
#   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#   //                SID/Label Sub-TLV (variable)                 //
#   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#
#         SR Node Cap Flags
# 				+
#      One or more entries, each of which have the following format:
#
#         Range Size: 3 octet value indicating the number of labels in
#         the range.
#
#         SID/Label sub-TLV (as defined in Section 2.3.7.2).


@LINKSTATE.register()
class SrCapabilities(object):
    TLV = 1034

    def __init__(self, sr_flags, sids):
        self.sr_flags = sr_flags
        self.sids = sids

    def __repr__(self):
        return "sr_capability_flags: %s, sids: %s" % (self.sr_flags, self.sids)

    @classmethod
    def unpack(cls, data, length):
        # Extract node capability flags
        flags = LsGenericFlags.unpack(data[0:1], LsGenericFlags.ISIS_SR_CAP_FLAGS)
        # Move pointer past flags and reserved bytes
        data = data[2:]
        sids = []
        while data:
            # Range Size: 3 octet value indicating the number of labels in
            # the range.
            b = BitArray(bytes=data[:3])
            range_size = b.unpack('uintbe:24')[0]
            # SID/Label: If length is set to 3, then the 20 rightmost bits
            # represent a label.  If length is set to 4, then the value
            # represents a 32 bit SID.
            t, l = unpack('!HH', data[3:7])
            if t != 1161:
                raise Notify(3, 5, "Invalid sub-TLV type: {}".format(t))
            v = data[7 : l + 7]
            if l == 3:
                b = BitArray(bytes=v)
                sid = b.unpack('uintbe:24')[0]
            elif l == 4:
                sid = unpack('!I', v)[0]
            sids.append((range_size, sid))
            data = data[l + 7 :]

        return cls(sr_flags=flags, sids=sids)

    def json(self, compact=None):
        return ', '.join(
            ['"sr-capability-flags": {}'.format(self.sr_flags.json()), '"sids": {}'.format(json.dumps(self.sids))]
        )
