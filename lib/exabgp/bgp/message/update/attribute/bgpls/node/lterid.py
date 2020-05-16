# encoding: utf-8
"""
nodename.py

Created by Evelio Vila on 2016-12-01.
Copyright (c) 2014-2017 Exa Networks. All rights reserved.
"""

from exabgp.protocol.ip import IP
from exabgp.bgp.message.notification import Notify

from exabgp.bgp.message.update.attribute.bgpls.linkstate import LinkState


#   |     1028    | IPv4 Router-ID of    |        4 | [RFC5305]/4.3     |
#   |             | Local Node           |          |                   |
#   |     1029    | IPv6 Router-ID of    |       16 | [RFC6119]/4.1     |
#   |             | Local Node           |          |                   |
#   +-------------+----------------------+----------+-------------------+
#   https://tools.ietf.org/html/rfc7752 sec 3.3.1.4  - Traffic Engineering RouterID


@LinkState.register(lsid=1028)
@LinkState.register(lsid=1029)
class LocalTeRid(object):
    _terids = []

    def __init__(self):
        self.terids = [str(terid) for terid in LocalTeRid._terids]

    def __repr__(self):
        return "Local TE Router IDs: %s" % ', '.join(self.terids)

    @classmethod
    def unpack(cls, data, length):
        size = len(data)

        if size not in (4, 16):
            raise Notify(3, 5, "Invalid remote-te size")

        terid = IP.unpack(data[:size])
        cls._terids.append(terid)
        return cls()

    def json(self, compact=None):
        return '"local-te-router-ids": ["%s"]' % '", "'.join(self.terids)

    @classmethod
    def reset(cls):
        cls._terids = []
