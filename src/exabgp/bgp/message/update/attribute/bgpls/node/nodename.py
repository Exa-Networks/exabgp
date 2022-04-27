# encoding: utf-8
"""
nodename.py

Created by Evelio Vila on 2016-12-01.
Copyright (c) 2014-2017 Exa Networks. All rights reserved.
"""

import json

from exabgp.bgp.message.notification import Notify

from exabgp.bgp.message.update.attribute.bgpls.linkstate import BaseLS
from exabgp.bgp.message.update.attribute.bgpls.linkstate import LinkState


#      0                   1                   2                   3
#      0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
#     +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#     |              Type             |             Length            |
#     +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#     //                     Node Name (variable)                    //
#     +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#     https://tools.ietf.org/html/rfc7752 Sec 3.3.1.3.  Node Name TLV


@LinkState.register()
class NodeName(BaseLS):
    TLV = 1026
    MERGE = False

    def __init__(self, nodename):
        BaseLS.__init__(self, nodename)

    def __repr__(self):
        return "nodename: %s" % (self.content)

    @classmethod
    def unpack(cls, data):
        if len(data) > 255:
            raise Notify(3, 5, "Node Name TLV length too large")

        return cls(data.decode('ascii'))

    def json(self, compact=None):
        return '"node-name": {}'.format(json.dumps(self.content))
