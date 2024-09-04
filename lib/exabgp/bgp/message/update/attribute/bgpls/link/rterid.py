# encoding: utf-8
"""
rterid.py

Created by Evelio Vila on 2016-12-01.
Copyright (c) 2014-2017 Exa Networks. All rights reserved.
"""

from exabgp.protocol.ip import IP
from exabgp.bgp.message.notification import Notify

from exabgp.bgp.message.update.attribute.bgpls.linkstate import LINKSTATE


#   |    1030   | IPv4 Router-ID of   |   134/---    | [RFC5305]/4.3    |
#   |           | Remote Node         |              |                  |
#   |    1031   | IPv6 Router-ID of   |   140/---    | [RFC6119]/4.1    |
#   |           | Remote Node         |              |                  |


@LINKSTATE.register(lsid=1030)
@LINKSTATE.register(lsid=1031)
class RemoteTeRid(object):
    def __init__(self, terid):
        self.terid = terid

    def __repr__(self):
        return "Remote TE Router ID: %s" % (self.terid)

    @classmethod
    def unpack(cls, data, length):
        if len(data) == 4:
            # IPv4 address
            terid = IP.unpack(data[:4])
        elif len(data) == 16:
            # IPv6
            terid = IP.unpack(data[:16])
        return cls(terid=terid)

    def json(self, compact=None):
        return '"remote-te-router-id": "%s"' % str(self.terid)
