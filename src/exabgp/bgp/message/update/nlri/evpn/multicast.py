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
        rd: RouteDistinguisher,
        etag: EthernetTag,
        ip: IP,
        packed: bytes | None = None,
        nexthop: IP = IP.NoNextHop,
        action: Action | None = None,
        addpath: PathInfo | None = None,
    ) -> None:
        EVPN.__init__(self, action, addpath)  # type: ignore[arg-type]
        self.nexthop = nexthop
        self.rd = rd
        self.etag = etag
        self.ip = ip
        self._pack(packed)

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

    def _pack(self, packed: bytes | None = None) -> bytes:
        if self._packed:
            return self._packed

        if packed:
            self._packed = packed
            return packed

        self._packed = self.rd.pack_rd() + self.etag.pack_etag() + bytes([len(self.ip) * 8]) + self.ip.pack_ip()  # type: ignore[arg-type]
        return self._packed

    @classmethod
    def unpack_evpn_route(cls, data: bytes) -> Multicast:
        rd = RouteDistinguisher.unpack_routedistinguisher(data[:8])
        etag = EthernetTag.unpack_etag(data[8:12])
        iplen = data[12]
        if iplen not in (4 * 8, 16 * 8):
            raise Exception('IP len is %d, but EVPN route currently support only IPv4' % iplen)
        ip = IP.unpack_ip(data[13 : 13 + iplen // 8])
        return cls(rd, etag, ip, data)

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
