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
class LocalTeRid(BaseLS):
    MERGE = True
    REPR = 'Local TE Router IDs'
    JSON = 'local-te-router-ids'

    def __init__(self, packed: bytes) -> None:
        self._packed = packed
        # For merge support, content is a list of packed bytes
        self._content_list: list[bytes] = [packed]

    @classmethod
    def unpack_bgpls(cls, data: bytes) -> LocalTeRid:
        length = len(data)

        if length not in (4, 16):
            raise Notify(3, 5, 'Invalid remote-te size')

        return cls(data)

    @property
    def content(self) -> list[str]:
        """List of TE Router IDs as strings."""
        return [str(IP.unpack_ip(data)) for data in self._content_list]

    def merge(self, other: 'LocalTeRid') -> None:
        """Merge another LocalTeRid's packed bytes into this one."""
        self._content_list.extend(other._content_list)

    def json(self, compact: bool = False) -> str:
        joined = '", "'.join(self.content)
        return f'"{self.JSON}": ["{joined}"]'
