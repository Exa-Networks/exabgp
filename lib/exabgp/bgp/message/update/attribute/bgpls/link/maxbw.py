# encoding: utf-8
"""
maxbw.py

Created by Evelio Vila on 2016-12-01.
Copyright (c) 2014-2017 Exa Networks. All rights reserved.
"""

from struct import unpack

from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.update.attribute.bgpls.linkstate import LINKSTATE

#  This sub-TLV contains the maximum bandwidth that can be used on this
#   link in this direction (from the system originating the LSP to its
#   neighbors).
#    https://tools.ietf.org/html/rfc5305#section-3.4
#
#  Units are in Bytes not Bits.
#  ----------------------------


@LINKSTATE.register()
class MaxBw(object):
    TLV = 1089

    def __init__(self, maxbw):
        self.maxbw = maxbw

    def __repr__(self):
        return "Maximum link bandwidth: %s" % (self.maxbw)

    @classmethod
    def unpack(cls, data, length):
        if length != 4:
            raise Notify(3, 5, "Incorrect maximum link bw metric")
        else:
            maxbw = unpack('!f', data)[0]
            return cls(maxbw=maxbw)

    def json(self, compact=None):
        return '"maximum-link-bandwidth": %s' % self.maxbw
