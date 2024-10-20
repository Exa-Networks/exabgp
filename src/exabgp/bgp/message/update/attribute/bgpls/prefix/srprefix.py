# encoding: utf-8
"""
srprefix.py

Created by Evelio Vila
Copyright (c) 2014-2017 Exa Networks. All rights reserved.
"""

import json
from struct import unpack
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


@LinkState.register()
class SrPrefix(FlagLS):
    TLV = 1158
    FLAGS = ['R', 'N', 'P', 'E', 'V', 'L', 'RSV', 'RSV']

    def __init__(self, flags, sids, sr_algo, undecoded=[]):
        self.flags = flags
        self.sids = sids
        self.sr_algo = sr_algo
        self.undecoded = undecoded

    def __repr__(self):
        return 'prefix_flags: %s, sids: %s, undecoded_sid: %s' % (self.flags, self.sids, self.undecoded)

    @classmethod
    def unpack(cls, data):
        # We only support IS-IS flags for now.
        flags = cls.unpack_flags(data[0:1])
        #
        # Parse Algorithm
        sr_algo = data[1]
        # Move pointer 4 bytes: Flags(1) + Algorithm(1) + Reserved(2)
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
            if flags['V'] and flags['L']:
                sid = unpack('!L', bytes([0]) + data[:3])[0]
                data = data[3:]
                sids.append(sid)
            elif (not flags['V']) and (not flags['L']):
                if len(data) != 4:
                    # Cisco IOS XR Software, Version 6.1.1.19I is not
                    # correctly setting the flags
                    raise Notify(3, 5, "SID/Label size doesn't match V and L flag state")
                sid = unpack('!I', data[:4])[0]
                data = data[4:]
                sids.append(sid)
            else:
                raw.append(hexstring(data))
                break

        return cls(flags=flags, sids=sids, sr_algo=sr_algo, undecoded=raw)

    def json(self, compact=None):
        return '"sr-prefix-flags": {}, "sids": {}, "undecoded-sids": {}, "sr-algorithm": {}'.format(
            json.dumps(self.flags),
            json.dumps(self.sids),
            json.dumps(self.undecoded),
            json.dumps(self.sr_algo),
        )
