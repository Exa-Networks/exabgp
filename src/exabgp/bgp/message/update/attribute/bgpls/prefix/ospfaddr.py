"""ospfaddr.py

Created by Evelio Vila on 2016-12-01.
Copyright (c) 2014-2017 Exa Networks. All rights reserved.
"""

from __future__ import annotations

from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.update.attribute.bgpls.linkstate import BaseLS, LinkState
from exabgp.protocol.ip import IP
from exabgp.util.types import Buffer

#      0                   1                   2                   3
#      0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
#     +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#     |              Type             |             Length            |
#     +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#     //                Forwarding Address (variable)                //
#     +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#     https://tools.ietf.org/html/rfc7752#section-3.3.3.5


@LinkState.register_lsid()
class OspfForwardingAddress(BaseLS):
    TLV = 1156
    REPR = 'Ospf forwarding address'
    JSON = 'ospf-forwarding-address'

    @property
    def content(self) -> str:
        """Unpack and return IP address string from packed bytes."""
        return IP.unpack_ip(self._packed).top()

    @classmethod
    def unpack_bgpls(cls, data: Buffer) -> OspfForwardingAddress:
        length = len(data)
        if length not in (4, 16):
            raise Notify(3, 5, 'Error parsing OSPF Forwarding Address. Wrong size')
        return cls(data)

    @classmethod
    def make_ospf_forwarding_address(cls, address: str) -> OspfForwardingAddress:
        """Create OspfForwardingAddress from IP address string."""
        return cls(IP.pton(address))
