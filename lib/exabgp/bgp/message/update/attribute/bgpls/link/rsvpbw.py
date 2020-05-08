# encoding: utf-8
"""
rsvpbw.py

Created by Evelio Vila on 2016-12-01.
Copyright (c) 2014-2017 Exa Networks. All rights reserved.
"""

from struct import unpack

from exabgp.bgp.message.notification import Notify

from exabgp.bgp.message.update.attribute.bgpls.linkstate import LINKSTATE


# This sub-TLV contains the maximum amount of bandwidth that can be
#   reserved in this direction on this link.  Note that for
#   oversubscription purposes, this can be greater than the bandwidth of
#   the link.
# https://tools.ietf.org/html/rfc5305#section-3.5
#
#  Units are in Bytes not Bits.
#  ----------------------------


@LINKSTATE.register()
class RsvpBw(object):
    TLV = 1090

    def __init__(self, rsvpbw):
        self.rsvpbw = rsvpbw

    def __repr__(self):
        return "Maximum reservable link bandwidth: %s" % (self.rsvpbw)

    @classmethod
    def unpack(cls, data, length):
        if len(data) != 4:
            raise Notify(3, 5, "Incorrect maximum reservable link bw metric")
        else:
            rsvpbw = unpack('!f', data)[0]
            return cls(rsvpbw=rsvpbw)

    def json(self, compact=None):
        return '"maximum-reservable-link-bandwidth": %s' % str(self.rsvpbw)
