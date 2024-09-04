# encoding: utf-8
"""
temetric.py

Created by Evelio Vila on 2016-12-01.
Copyright (c) 2014-2017 Exa Networks. All rights reserved.
"""
from struct import unpack

from exabgp.bgp.message.notification import Notify

from exabgp.bgp.message.update.attribute.bgpls.linkstate import LINKSTATE


#     0                   1                   2                   3
#     0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
#    +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#    |              Type             |             Length            |
#    +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#    |                    TE Default Link Metric                     |
#    +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#    https://tools.ietf.org/html/rfc7752#section-3.3.2.3 TE Metric


@LINKSTATE.register()
class TeMetric(object):
    TLV = 1092

    def __init__(self, temetric):
        self.temetric = temetric

    def __repr__(self):
        return "TE Default Metric: %s" % (self.temetric)

    @classmethod
    def unpack(cls, data, length):
        if len(data) != 4:
            raise Notify(3, 5, "Incorrect TE Metric Size")
        else:
            temetric = unpack('!L', data)[0]
            return cls(temetric=temetric)

    def json(self, compact=None):
        return '"te-metric": %d' % int(str(self.temetric))
