# encoding: utf-8
"""
sralgo.py

Created by Evelio Vila
Copyright (c) 2014-2017 Exa Networks. All rights reserved.
"""

import json
from struct import unpack
from exabgp.vendoring import six

from exabgp.bgp.message.update.attribute.bgpls.linkstate import LINKSTATE

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


@LINKSTATE.register()
class SrAlgorithm(object):
    TLV = 1035

    def __init__(self, sr_algos):
        self.sr_algos = sr_algos

    def __repr__(self):
        return "SrAlgorithms: %s" % (self.sr_algos)

    @classmethod
    def unpack(cls, data, length):
        sr_algos = []
        while data:
            sr_algos.append(six.indexbytes(data, 0))
            data = data[1:]
        # Looks like IOS XR advertises len 0 on this sub TLV
        # when using default SPF.
        if not len(sr_algos):
            sr_algos.append(0)
        return cls(sr_algos=sr_algos)

    def json(self, compact=None):
        return '"sr-algorithms": {}'.format(json.dumps(self.sr_algos))
