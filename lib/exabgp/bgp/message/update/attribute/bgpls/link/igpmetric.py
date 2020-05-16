# encoding: utf-8
"""
igpmetric.py

Created by Evelio Vila on 2016-12-01.
Copyright (c) 2014-2017 Exa Networks. All rights reserved.
"""

from struct import unpack

from exabgp.bgp.message.notification import Notify

from exabgp.bgp.message.update.attribute.bgpls.linkstate import LinkState


#   The IGP Metric TLV carries the metric for this link.  The length of
#   this TLV is variable, depending on the metric width of the underlying
#   protocol.  IS-IS small metrics have a length of 1 octet (the two most
#   significant bits are ignored).  OSPF link metrics have a length of 2
#   octets.  IS-IS wide metrics have a length of 3 octets.
#
#      0                   1                   2                   3
#      0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
#     +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#     |              Type             |             Length            |
#     +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#     //      IGP Link Metric (variable length)      //
#     +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+


@LinkState.register()
class IgpMetric(object):
    TLV = 1095

    def __init__(self, igpmetric):
        self.igpmetric = igpmetric

    def __repr__(self):
        return "IGP Metric: %s" % (self.igpmetric)

    @classmethod
    def unpack(cls, data, length):
        if len(data) == 2:
            # OSPF
            return cls(unpack('!H', data)[0])

        if len(data) == 1:
            # ISIS small metrics
            return cls(data[0])

        if len(data) == 3:
            # ISIS wide metrics
            return cls(unpack('!L', bytes([0]) + data)[0])

        raise Notify(3, 5, "Incorrect IGP Metric Size")

    def json(self, compact=None):
        return '"igp-metric": %d' % int(self.igpmetric[0])
