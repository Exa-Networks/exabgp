# encoding: utf-8
"""
srv6locator.py

Created by Quentin De Muynck
Copyright (c) 2025 Exa Networks. All rights reserved.
"""

from __future__ import annotations

import json
from struct import unpack

from exabgp.bgp.message.update.attribute.bgpls.linkstate import FlagLS
from exabgp.bgp.message.update.attribute.bgpls.linkstate import LinkState

#    RFC 9514:  5.1.  SRv6 Locator TLV
#     0                   1                   2                   3
#     0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
#    +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#    |               Type            |          Length               |
#    +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#    |      Flags    |   Algorithm   |           Reserved            |
#    +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#    |                            Metric                             |
#    +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#    |   Sub-TLVs (variable) . . .
#    +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#
#                      Figure 4: SRv6 Locator TLV Format

@LinkState.register()
class Srv6Locator(FlagLS):
    TLV = 1162
    FLAGS = ['D'] + ['RSV' for _ in range(7)] 
    registered_subsubtlvs = dict()

    def __init__(self, flags, algorithm, metric, subtlvs):
        self.flags = flags
        self.algorithm = algorithm
        self.metric = metric
        self.subtlvs = subtlvs

    def __repr__(self):
        return 'flags: %s, algorithm: %s, metric: %s' % (self.flags, self.algorithm, self.metric)

    @classmethod
    def unpack(cls, data):
        flags = cls.unpack_flags(bytes(data[0:1]))
        algorithm = data[1]
        metric = unpack('!I', data[4:8])[0]
        subtlvs = [] # No sub-TLVs defined in RFC 9514

        return cls(flags=flags, algorithm=algorithm, metric=metric, subtlvs=subtlvs)

    def json(self, compact=None):
        return '"srv6-locator": ' + json.dumps({
            'flags': self.flags,
            'algorithm': self.algorithm,
            'metric': self.metric,
        }, indent=compact)
