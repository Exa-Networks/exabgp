"""srrid.py

Created by Evelio Vila
Copyright (c) 2014-2017 Exa Networks. All rights reserved.
"""

from __future__ import annotations

from exabgp.protocol.ip import IP

from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.update.attribute.bgpls.linkstate import LinkState
from exabgp.bgp.message.update.attribute.bgpls.linkstate import BaseLS
from exabgp.util.types import Buffer

#    draft-gredler-idr-bgp-ls-segment-routing-ext-03
#    0                   1                   2                   3
#    0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
#   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#   |            Type               |            Length             |
#   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#   //                  IPv4/IPv6 Address (Router-ID)              //
#   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#     Source Router Identifier (Source Router-ID) TLV


@LinkState.register_lsid(tlv=1171, json_key='sr-source-router-id', repr_name='Source router identifier')
class SourceRouterId(BaseLS):
    @property
    def content(self) -> str:
        """Unpack and return IP address string from packed bytes."""
        return str(IP.create_ip(self._packed))

    @classmethod
    def unpack_bgpls(cls, data: Buffer) -> SourceRouterId:
        length = len(data)
        if length not in (4, 16):
            raise Notify(3, 5, 'Error parsing SR Source Router ID. Wrong size')
        return cls(data)

    @classmethod
    def make_source_router_id(cls, address: str) -> SourceRouterId:
        """Create SourceRouterId from IP address string."""
        return cls(IP.pton(address))
