# encoding: utf-8
"""
sralgo.py

Created by Evelio Vila
Copyright (c) 2014-2017 Exa Networks. All rights reserved.
"""

import json

from exabgp.bgp.message.update.attribute.bgpls.linkstate import BaseLS
from exabgp.bgp.message.update.attribute.bgpls.linkstate import LinkState

#     draft-gredler-idr-bgp-ls-segment-routing-ext-03
#    0                   1                   2                   3
#    0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
#   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#   |            Type               |            Length             |
#   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#   |  Algorithm 1  |  Algorithm... |  Algorithm N |                |
#   +-                                                             -+
#   |                                                               |
#   +                                                               +
# 						sec 2.1.2.


@LinkState.register()
class SrAlgorithm(BaseLS):
    TLV = 1035

    def __init__(self, sr_algos):
        BaseLS.__init__(self, sr_algos)

    def __repr__(self):
        return "SrAlgorithms: %s" % (self.content)

    @classmethod
    def unpack(cls, data):
        # Looks like IOS XR advertises len 0 on this sub TLV
        # when using default SPF.
        return cls(
            [_ for _ in data]
            or [
                0,
            ]
        )

    def json(self, compact=None):
        return '"sr-algorithms": {}'.format(json.dumps(self.content))
