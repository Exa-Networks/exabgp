# encoding: utf-8
"""
sradjlan.py

Created by Evelio Vila
Copyright (c) 2014-2017 Exa Networks. All rights reserved.
"""

import json
from struct import unpack
from exabgp.util import hexstring

from exabgp.protocol.iso import ISO
from exabgp.bgp.message.update.attribute.bgpls.linkstate import LINKSTATE
from exabgp.bgp.message.update.attribute.bgpls.linkstate import LsGenericFlags


#   0                   1                   2                   3
#   0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
#  +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#  |              Type             |            Length             |
#  +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#  |     Flags     |     Weight    |            Reserved           |
#  +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#
#   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#   |             OSPF Neighbor ID / IS-IS System-ID                |
#   +                               +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#   |                               |
#   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#
#   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#   |                    SID/Label/Index (variable)                 |
#   +---------------------------------------------------------------+
# 		draft-gredler-idr-bgp-ls-segment-routing-ext-03

#  draft-ietf-isis-segment-routing-extensions - Adj-SID IS-IS Flags

@LINKSTATE.register()
class SrAdjacencyLan(LsGenericFlags):
    TLV = 1100
    FLAGS = ['F', 'B', 'V', 'L', 'S', 'P', 'RSV', 'RSV']

    def __init__(self, flags, sids, weight, system_id, undecoded=[]):
        self.flags = flags
        self.sids = sids
        self.weight = weight
        self.undecoded = undecoded
        self.system_id = system_id

    def __repr__(self):
        return "sr_adj_lan_flags: %s, sids: %s, undecoded_sid: %s" % (self.flags, self.sids, self.undecoded)

    @classmethod
    def unpack(cls, data, length):
        # We only support IS-IS flags for now.
        flags = cls.unpack_flags(data[0:1])
        # Parse adj weight
        weight = data[1]
        # Move pointer 4 bytes: Flags(1) + Weight(1) + Reserved(2)
        system_id = ISO.unpack_sysid(data[4:10])
        data = data[10:]
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
                sid = unpack('!L', bytes([0]) + data[:3])[0]
                data = data[3:]
                sids.append(sid)
            elif (not flags.flags['V']) and (not flags.flags['L']):
                sid = unpack('!I', data[:4])[0]
                data = data[4:]
                sids.append(sid)
            else:
                raw.append(hexstring(data))
                break

        return cls(flags=flags, sids=sids, weight=weight, system_id=system_id, undecoded=raw)

    def json(self, compact=None):
        return json.dumps({
            'sr-adj-lan-flags': self.flags,
            'sids': self.sids,
            'undecoded-sids': self.undecoded,
            'sr-adj-lan-weight': self.weight,
            'system-id': self.sytemd_id
        })
