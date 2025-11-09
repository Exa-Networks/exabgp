
"""rterid.py

Created by Evelio Vila on 2016-12-01.
Copyright (c) 2014-2017 Exa Networks. All rights reserved.
"""

from __future__ import annotations

from exabgp.protocol.ip import IP
from exabgp.bgp.message.notification import Notify

from exabgp.bgp.message.update.attribute.bgpls.linkstate import LinkState
from exabgp.bgp.message.update.attribute.bgpls.linkstate import BaseLS


#   |    1030   | IPv4 Router-ID of   |   134/---    | [RFC5305]/4.3    |
#   |           | Remote Node         |              |                  |
#   |    1031   | IPv6 Router-ID of   |   140/---    | [RFC6119]/4.1    |
#   |           | Remote Node         |              |                  |


@LinkState.register(lsid=1030)
@LinkState.register(lsid=1031)
class RemoteTeRid(BaseLS):
    REPR = 'Remote TE Router ID'
    JSON = 'remote-te-router-id'

    @classmethod
    def unpack(cls, data):
        length = len(data)
        if length not in (4, 16):
            raise Notify(3, 5, 'Invalid remote-te size')
        return cls(IP.unpack(data))
