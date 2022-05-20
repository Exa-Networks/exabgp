# encoding: utf-8
"""
maxbw.py

Created by Evelio Vila on 2016-12-01.
Copyright (c) 2014-2017 Exa Networks. All rights reserved.
"""

from struct import unpack

from exabgp.bgp.message.update.attribute.bgpls.linkstate import LinkState
from exabgp.bgp.message.update.attribute.bgpls.linkstate import BaseLS

#  This sub-TLV contains the maximum bandwidth that can be used on this
#   link in this direction (from the system originating the LSP to its
#   neighbors).
#    https://tools.ietf.org/html/rfc5305#section-3.4
#
#  Units are in Bytes not Bits.
#  ----------------------------


@LinkState.register()
class MaxBw(BaseLS):
    TLV = 1089
    REPR = 'Maximum link bandwidth'
    JSON = 'maximum-link-bandwidth'
    LEN = 4

    @classmethod
    def unpack(cls, data):
        cls.check(data)
        return cls(unpack('!f', data)[0])
