"""rterid.py

Created by Evelio Vila on 2016-12-01.
Copyright (c) 2014-2017 Exa Networks. All rights reserved.
"""

from __future__ import annotations

from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.update.attribute.bgpls.linkstate import BaseLS, LinkState
from exabgp.protocol.ip import IP
from exabgp.util.types import Buffer

#   |    1030   | IPv4 Router-ID of   |   134/---    | [RFC5305]/4.3    |
#   |           | Remote Node         |              |                  |
#   |    1031   | IPv6 Router-ID of   |   140/---    | [RFC6119]/4.1    |
#   |           | Remote Node         |              |                  |


@LinkState.register_lsid(lsid=1030)
@LinkState.register_lsid(lsid=1031)
class RemoteRouterId(BaseLS):
    REPR = 'Remote Router ID'
    JSON = 'remote-router-id'

    @property
    def content(self) -> str:
        """Unpack and return the IP address as a string."""
        return IP.create_ip(self._packed).top()

    @classmethod
    def make_remoterouterid(cls, ip: str) -> RemoteRouterId:
        """Factory method to create RemoteRouterId from IP address string."""
        return cls(IP.pton(ip))

    @classmethod
    def unpack_bgpls(cls, data: Buffer) -> RemoteRouterId:
        length = len(data)
        if length not in (4, 16):
            raise Notify(3, 5, 'Invalid remote-te size')
        return cls(data)
