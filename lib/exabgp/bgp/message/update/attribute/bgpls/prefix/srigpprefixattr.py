# encoding: utf-8
"""
srigpprefixattr.py

Created by Evelio Vila
Copyright (c) 2014-2017 Exa Networks. All rights reserved.
"""

import json

from exabgp.bgp.message.update.attribute.bgpls.linkstate import LINKSTATE, LsGenericFlags

#    draft-gredler-idr-bgp-ls-segment-routing-ext-03
#    0                   1                   2                   3
#    0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
#   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#   |            Type               |            Length             |
#   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#   //                       Flags (variable)                      //
#   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+


@LINKSTATE.register()
class SrIgpPrefixAttr(object):
    TLV = 1170

    def __init__(self, flags):
        self.flags = flags

    def __repr__(self):
        return "prefix_attr_flags: %s" % (self.flags)

    @classmethod
    def unpack(cls, data, length):
        # We only support IS-IS for now.
        flags = LsGenericFlags.unpack(data[0:1], LsGenericFlags.ISIS_SR_ATTR_FLAGS)
        return cls(flags=flags)

    def json(self, compact=None):
        return '"sr-prefix-attribute-flags": {}'.format(self.flags.json())
