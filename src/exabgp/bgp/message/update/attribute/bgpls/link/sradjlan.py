"""sradjlan.py

Created by Evelio Vila
Copyright (c) 2014-2017 Exa Networks. All rights reserved.
"""

from __future__ import annotations

import json
from struct import unpack
from exabgp.util import hexstring

from exabgp.protocol.iso import ISO
from exabgp.bgp.message.update.attribute.bgpls.linkstate import LinkState
from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.update.attribute.bgpls.linkstate import FlagLS


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


@LinkState.register()
class SrAdjacencyLan(FlagLS):
    TLV = 1100
    FLAGS = ['F', 'B', 'V', 'L', 'S', 'P', 'RSV', 'RSV']
    MERGE = True

    HEADER_SIZE = 4  # Flags(1) + Weight(1) + Reserved(2)
    SYSTEM_ID_SIZE = 6
    SID_LABEL_SIZE = 3  # V and L set: a 3 octet local label
    SID_INDEX_SIZE = 4  # V and L unset: a 4 octet index

    def __init__(self, sradjlans):
        # this used to drop its argument, so the JSON always showed an empty list
        self.sr_adj_lan_sids = list(sradjlans)

    def __repr__(self):
        return f'sr-adj-lan-sids: {self.sr_adj_lan_sids}'

    @classmethod
    def unpack(cls, data):
        if len(data) < cls.HEADER_SIZE + cls.SYSTEM_ID_SIZE:
            raise Notify(3, 5, f'Unable to decode attribute, not enough data for {cls.REPR}')
        # We only support IS-IS flags for now.
        flags = cls.unpack_flags(data[0:1])
        # Parse adj weight
        weight = data[1]
        # Move pointer 4 bytes: Flags(1) + Weight(1) + Reserved(2)
        system_id = ISO.unpack_sysid(data[cls.HEADER_SIZE : cls.HEADER_SIZE + cls.SYSTEM_ID_SIZE])
        data = data[cls.HEADER_SIZE + cls.SYSTEM_ID_SIZE :]
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
                if len(data) < cls.SID_LABEL_SIZE:
                    raise Notify(3, 5, f'Unable to decode attribute, truncated SID in {cls.REPR}')
                sid = unpack('!L', bytes([0]) + data[: cls.SID_LABEL_SIZE])[0]
                data = data[cls.SID_LABEL_SIZE :]
                sids.append(sid)
            elif (not flags['V']) and (not flags['L']):
                if len(data) < cls.SID_INDEX_SIZE:
                    raise Notify(3, 5, f'Unable to decode attribute, truncated SID in {cls.REPR}')
                sid = unpack('!I', data[: cls.SID_INDEX_SIZE])[0]
                data = data[cls.SID_INDEX_SIZE :]
                sids.append(sid)
            else:
                raw.append(hexstring(data))
                break

        return cls([{'flags': flags, 'weight': weight, 'system-id': system_id, 'sids': sids, 'undecoded': raw}])

    def json(self, compact=None):
        return f'"sr-adj-lan-sids": {json.dumps(self.sr_adj_lan_sids)}'

    def as_dict(self):
        return {'sr-adj-lan-sids': self.sr_adj_lan_sids}

    def merge(self, klass):
        self.sr_adj_lan_sids.extend(klass.sr_adj_lan_sids)
