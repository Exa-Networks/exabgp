# encoding: utf-8
"""
linkname.py

Created by Evelio Vila on 2016-12-01.
Copyright (c) 2014-2017 Exa Networks. All rights reserved.
"""

import binascii

from exabgp.bgp.message.notification import Notify

from exabgp.bgp.message.update.attribute.bgpls.linkstate import LINKSTATE


#      0                   1                   2                   3
#      0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
#     +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#     |              Type             |             Length            |
#     +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#     //                     Link Name (variable)                    //
#     +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#     https://tools.ietf.org/html/rfc7752#section-3.3.2.7  Link Name TLV


@LINKSTATE.register()
class LinkName(object):
    TLV = 1098

    def __init__(self, linkname):
        self.linkname = linkname

    def __repr__(self):
        return "linkname: %s" % (self.linkname)

    @classmethod
    def unpack(cls, data, length):
        if length > 255:
            raise Notify(3, 5, "Link Name TLV length too large")
        else:
            linkname = binascii.b2a_uu(data[:length])
            return cls(linkname=linkname)

    def json(self, compact=None):
        return '"link-name": "%s"' % self.linkname
