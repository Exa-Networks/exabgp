"""segment.py

Created by Thomas Mangin on 2014-06-27.
Copyright (c) 2014-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from typing import Any, ClassVar, Optional

from exabgp.protocol.ip import IP

from exabgp.bgp.message.update.nlri.qualifier import RouteDistinguisher
from exabgp.bgp.message.update.nlri.qualifier import ESI

from exabgp.bgp.message.update.nlri.evpn.nlri import EVPN
from exabgp.bgp.message import Action

from exabgp.bgp.message.notification import Notify

# +---------------------------------------+
# |      RD   (8 octets)                  |
# +---------------------------------------+
# |Ethernet Segment Identifier (10 octets)|
# +---------------------------------------+
# |  IP Address Length (1 octet)          |
# +---------------------------------------+
# |   Originating Router's IP Addr        |
# |          (4 or 16 octets)             |
# +---------------------------------------+

# ===================================================================== EVPNNLRI


@EVPN.register
class EthernetSegment(EVPN):
    CODE: ClassVar[int] = 4
    NAME: ClassVar[str] = 'Ethernet Segment'
    SHORT_NAME: ClassVar[str] = 'Segment'

    def __init__(
        self,
        rd: RouteDistinguisher,
        esi: ESI,
        ip: IP,
        packed: Optional[bytes] = None,
        nexthop: Any = None,
        action: Optional[Action] = None,
        addpath: Any = None,
    ) -> None:
        EVPN.__init__(self, action, addpath)  # type: ignore[arg-type]
        self.nexthop = nexthop
        self.rd = rd
        self.esi = esi
        self.ip = ip
        self._pack(packed)

    def __eq__(self, other: object) -> bool:
        return (
            isinstance(other, EthernetSegment)
            and self.CODE == other.CODE
            and self.rd == other.rd
            and self.ip == other.ip
        )
        # esi and label must not be part of the comparaison

    def __ne__(self, other: object) -> bool:
        return not self.__eq__(other)

    def __str__(self) -> str:
        return '{}:{}:{}:{}'.format(self._prefix(), self.rd._str(), self.esi, self.ip if self.ip else '')

    def __hash__(self) -> int:
        # esi and label MUST *NOT* be part of the hash
        return hash((self.rd, self.ip))

    def _pack(self, packed: Optional[bytes] = None) -> bytes:
        if self._packed:
            return self._packed

        if packed:
            self._packed = packed
            return packed

        # fmt: off
        self._packed = (
            self.rd.pack_rd()
            + self.esi.pack_esi()
            + bytes([len(self.ip) * 8 if self.ip else 0]) # type: ignore[arg-type]
            + self.ip.pack_ip() if self.ip else b''
        )
        # fmt: on
        return self._packed

    @classmethod
    def unpack_evpn_route(cls, data: bytes) -> EthernetSegment:
        rd = RouteDistinguisher.unpack_routedistinguisher(data[:8])
        esi = ESI.unpack_esi(data[8:18])
        iplen = data[18]

        if iplen not in (32, 128):
            raise Notify(
                3,
                5,
                'IP length field is given as %d in current Segment, expecting 32 (IPv4) or 128 (IPv6) bits' % iplen,
            )

        ip = IP.unpack_ip(data[19 : 19 + (iplen // 8)])

        return cls(rd, esi, ip, data)

    def json(self, compact: Optional[bool] = None) -> str:
        content = ' "code": %d, ' % self.CODE
        content += '"parsed": true, '
        content += '"raw": "{}", '.format(self._raw())
        content += '"name": "{}", '.format(self.NAME)
        content += '{}, '.format(self.rd.json())
        content += self.esi.json()
        content += ', "ip": "{}"'.format(str(self.ip))
        return '{{{} }}'.format(content)
