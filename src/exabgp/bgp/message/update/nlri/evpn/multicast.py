"""multicast.py

Created by Thomas Morin on 2014-06-23.
Copyright (c) 2014-2017 Orange. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from typing import ClassVar

from exabgp.bgp.message.update.nlri.qualifier.path import PathInfo
from exabgp.protocol.ip import IP
from exabgp.bgp.message.update.nlri.qualifier import RouteDistinguisher
from exabgp.bgp.message.update.nlri.qualifier import EthernetTag

from exabgp.bgp.message.update.nlri.evpn.nlri import EVPN
from exabgp.bgp.message import Action

# +---------------------------------------+
# |      RD   (8 octets)                  |
# +---------------------------------------+
# |  Ethernet Tag ID (4 octets)           |
# +---------------------------------------+
# |  IP Address Length (1 octet)          |
# +---------------------------------------+
# |   Originating Router's IP Addr        |
# |          (4 or 16 octets)             |
# +---------------------------------------+

# ===================================================================== EVPNNLRI


@EVPN.register
class Multicast(EVPN):
    CODE: ClassVar[int] = 3
    NAME: ClassVar[str] = 'Inclusive Multicast Ethernet Tag'
    SHORT_NAME: ClassVar[str] = 'Multicast'

    def __init__(
        self,
        packed: bytes,
        nexthop: IP = IP.NoNextHop,
        action: Action | None = None,
        addpath: PathInfo | None = None,
    ) -> None:
        EVPN.__init__(self, action, addpath)  # type: ignore[arg-type]
        self._packed = packed
        self.nexthop = nexthop

    @classmethod
    def make_multicast(
        cls,
        rd: RouteDistinguisher,
        etag: EthernetTag,
        ip: IP,
        nexthop: IP = IP.NoNextHop,
        action: Action | None = None,
        addpath: PathInfo | None = None,
    ) -> 'Multicast':
        """Factory method to create Multicast from semantic parameters."""
        packed = rd.pack_rd() + etag.pack_etag() + bytes([len(ip) * 8]) + ip.pack_ip()  # type: ignore[arg-type]
        return cls(packed, nexthop, action, addpath)

    @property
    def rd(self) -> RouteDistinguisher:
        return RouteDistinguisher.unpack_routedistinguisher(self._packed[:8])

    @property
    def etag(self) -> EthernetTag:
        return EthernetTag.unpack_etag(self._packed[8:12])

    @property
    def ip(self) -> IP:
        iplen = self._packed[12]
        return IP.unpack_ip(self._packed[13 : 13 + iplen // 8])

    def __ne__(self, other: object) -> bool:
        return not self.__eq__(other)

    def __str__(self) -> str:
        return '{}:{}:{}:{}'.format(
            self._prefix(),
            self.rd._str(),
            self.etag,
            self.ip,
        )

    def __hash__(self) -> int:
        return hash((self.afi, self.safi, self.CODE, self.rd, self.etag, self.ip))

    @classmethod
    def unpack_evpn_route(cls, data: bytes) -> Multicast:
        iplen = data[12]
        if iplen not in (4 * 8, 16 * 8):
            raise Exception('IP len is %d, but EVPN route currently support only IPv4' % iplen)
        return cls(data)

    def json(self, compact: bool | None = None) -> str:
        content = ' "code": %d, ' % self.CODE
        content += '"parsed": true, '
        content += '"raw": "{}", '.format(self._raw())
        content += '"name": "{}", '.format(self.NAME)
        content += '{}, '.format(self.rd.json())
        content += self.etag.json()
        if self.ip:
            content += ', "ip": "{}"'.format(str(self.ip))
        return '{{{} }}'.format(content)
