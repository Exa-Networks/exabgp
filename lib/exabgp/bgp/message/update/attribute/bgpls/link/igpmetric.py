# encoding: utf-8
"""
igpmetric.py

Created by Evelio Vila on 2016-12-01.
Copyright (c) 2014-2017 Exa Networks. All rights reserved.
"""

from struct import unpack
from exabgp.vendoring import six

from exabgp.vendoring.bitstring import BitArray
from exabgp.bgp.message.notification import Notify

from exabgp.bgp.message.update.attribute.bgpls.linkstate import LINKSTATE


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


@LINKSTATE.register()
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
            igpmetric = unpack('!H', data)[0]
            return cls(igpmetric=igpmetric)
        elif len(data) == 1:
            # ISIS small metrics
            igpmetric = six.indexbytes(data, 0)
            return cls(igpmetric=igpmetric)
        elif len(data) == 3:
            # ISIS wide metrics
            b = BitArray(bytes=data)
            igpmetric = b.unpack('uintbe:24')
            return cls(igpmetric=igpmetric)
        else:
            raise Notify(3, 5, "Incorrect IGP Metric Size")

    def json(self, compact=None):
        return '"igp-metric": %d' % int(self.igpmetric[0])
