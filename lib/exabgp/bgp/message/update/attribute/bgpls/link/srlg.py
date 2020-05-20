# encoding: utf-8
"""
srlg.py

Created by Evelio Vila on 2016-12-01.
Copyright (c) 2014-2017 Exa Networks. All rights reserved.
"""

from struct import unpack

from exabgp.bgp.message.notification import Notify

from exabgp.bgp.message.update.attribute.bgpls.linkstate import LINKSTATE


#      0                   1                   2                   3
#      0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
#     +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#     |              Type             |             Length            |
#     +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#     |                  Shared Risk Link Group Value                 |
#     +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#     //                         ............                        //
#     +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#     |                  Shared Risk Link Group Value                 |
#     +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#     https://tools.ietf.org/html/rfc7752#section-3.3.2.5 Shared Risk Link Group TLV


@LINKSTATE.register()
class Srlg(object):
    TLV = 1096

    def __init__(self, srlg):
        self.srlg = srlg

    def __repr__(self):
        return "SRLG values on link are: %s" % (self.srlg)

    @classmethod
    def unpack(cls, data, length):
        srlg = []
        if len(data) < 4:
            raise Notify(3, 5, "Unable to decode SRLG")
        while data:
            lgrp = unpack('!L', data[:4])[0]
            srlg.append(lgrp)
            data = data[4:]
        return cls(srlg=srlg)

    def json(self, compact=None):
        return '"shared-risk-link-groups": %s' % str(self.srlg)
