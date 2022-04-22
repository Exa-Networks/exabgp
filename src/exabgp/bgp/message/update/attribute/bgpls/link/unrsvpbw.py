# encoding: utf-8
"""
nunrsvpbw.py

Created by Evelio Vila on 2016-12-01.
Copyright (c) 2014-2017 Exa Networks. All rights reserved.
"""

from struct import unpack

from exabgp.bgp.message.notification import Notify

from exabgp.bgp.message.update.attribute.bgpls.linkstate import LinkState
from exabgp.bgp.message.update.attribute.bgpls.linkstate import BaseLS


#   This sub-TLV contains the amount of bandwidth reservable in this
#   direction on this link.  Note that for oversubscription purposes,
#   this can be greater than the bandwidth of the link.
#    [ One value per priority]
#   https://tools.ietf.org/html/rfc5305#section-3.6
#
#  Units are in Bytes not Bits.
#  ----------------------------


@LinkState.register()
class UnRsvpBw(BaseLS):
    TLV = 1091
    REPR = 'Maximum link bandwidth'
    JSON = 'unreserved-bandwidth'
    LEN = 32

    @classmethod
    def unpack(cls, data):
        cls.check(data)
        return cls(unpack('!ffffffff', data))
