# encoding: utf-8
"""
nunrsvpbw.py

Created by Evelio Vila on 2016-12-01.
Copyright (c) 2014-2017 Exa Networks. All rights reserved.
"""

from struct import unpack

from exabgp.bgp.message.notification import Notify

from exabgp.bgp.message.update.attribute.bgpls.linkstate import LINKSTATE


#   This sub-TLV contains the amount of bandwidth reservable in this
#   direction on this link.  Note that for oversubscription purposes,
#   this can be greater than the bandwidth of the link.
#    [ One value per priority]
#   https://tools.ietf.org/html/rfc5305#section-3.6
#
#  Units are in Bytes not Bits.
#  ----------------------------


@LINKSTATE.register()
class UnRsvpBw(object):
    TLV = 1091

    def __init__(self, unrsvpbw):
        self.unrsvpbw = unrsvpbw

    def __repr__(self):
        return "Maximum link bandwidth: %s" % (self.unrsvpbw)

    @classmethod
    def unpack(cls, data, length):
        if length != 32:
            raise Notify(3, 5, "Wrong Unreservable Bw metric size")
        else:
            unrsvpbw = [p for p in unpack('!ffffffff', data)]
            return cls(unrsvpbw=unrsvpbw)

    def json(self, compact=None):
        return '"unreserved-bandwidth": %s' % str(self.unrsvpbw)
