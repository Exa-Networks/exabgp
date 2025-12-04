"""ospfaddr.py

Created by Evelio Vila on 2016-12-01.
Copyright (c) 2014-2017 Exa Networks. All rights reserved.
"""

from __future__ import annotations

from exabgp.protocol.ip import IP

from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.update.attribute.bgpls.linkstate import LinkState
from exabgp.bgp.message.update.attribute.bgpls.linkstate import BaseLS

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
        return IP.unpack_ip(self._packed)

    @classmethod
    def unpack_bgpls(cls, data: bytes) -> OspfForwardingAddress:
        length = len(data)
        if length not in (4, 16):
            raise Notify(3, 5, 'Error parsing OSPF Forwarding Address. Wrong size')
        return cls(data)
