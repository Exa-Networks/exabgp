# encoding: utf-8
"""
nodename.py

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
#     //                     Node Name (variable)                    //
#     +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#     https://tools.ietf.org/html/rfc7752 Sec 3.3.1.3.  Node Name TLV


@LINKSTATE.register()
class NodeName(object):
    TLV = 1026

    def __init__(self, nodename):
        self.nodename = nodename

    def __repr__(self):
        return "nodename: %s" % (self.nodename)

    @classmethod
    def unpack(cls, data, length):
        if length > 255:
            raise Notify(3, 5, "Node Name TLV length too large")
        else:
            nodename = data[:length].decode('ascii')
            return cls(nodename=nodename)

    def json(self, compact=None):
        return '"node-name": "%s"' % str(self.nodename)
