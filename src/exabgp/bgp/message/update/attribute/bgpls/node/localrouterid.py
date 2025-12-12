"""nodename.py

Created by Evelio Vila on 2016-12-01.
Copyright (c) 2014-2017 Exa Networks. All rights reserved.
"""

from __future__ import annotations

from exabgp.protocol.ip import IP
from exabgp.bgp.message.notification import Notify

from exabgp.bgp.message.update.attribute.bgpls.linkstate import BaseLS
from exabgp.bgp.message.update.attribute.bgpls.linkstate import LinkState


#   |     1028    | IPv4 Router-ID of    |        4 | [RFC5305]/4.3     |
#   |             | Local Node           |          |                   |
#   |     1029    | IPv6 Router-ID of    |       16 | [RFC6119]/4.1     |
#   |             | Local Node           |          |                   |
#   +-------------+----------------------+----------+-------------------+
#   https://tools.ietf.org/html/rfc7752 sec 3.3.1.4  - Traffic Engineering RouterID


@LinkState.register_lsid(lsid=1028)
@LinkState.register_lsid(lsid=1029)
class LocalRouterId(BaseLS):
    MERGE = True  # LinkState.json() groups into array
    REPR = 'Local Router IDs'
    JSON = 'local-router-ids'

    def __init__(self, packed: bytes) -> None:
        self._packed = packed

    @classmethod
    def unpack_bgpls(cls, data: bytes) -> LocalRouterId:
        length = len(data)

        if length not in (4, 16):
            raise Notify(3, 5, 'Invalid remote-te size')

        return cls(data)

    @property
    def content(self) -> str:
        """TE Router ID as string."""
        return str(IP.unpack_ip(self._packed))

    def json(self, compact: bool = False) -> str:
        return f'"{self.JSON}": ["{self.content}"]'

    @classmethod
    def make_local_router_id(cls, address: str) -> LocalRouterId:
        """Create LocalRouterId from IP address string.

        Args:
            address: IPv4 or IPv6 address string

        Returns:
            LocalRouterId instance with packed wire-format bytes
        """
        return cls(IP.pton(address))
