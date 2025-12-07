"""segment.py

Created by Thomas Mangin on 2014-06-27.
Copyright (c) 2014-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from typing import Any, ClassVar

from exabgp.bgp.message import Action
from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.update.nlri.evpn.nlri import EVPN
from exabgp.bgp.message.update.nlri.qualifier import ESI, RouteDistinguisher
from exabgp.protocol.ip import IP
from exabgp.util.types import Buffer

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


@EVPN.register_evpn_route
class EthernetSegment(EVPN):
    CODE: ClassVar[int] = 4
    NAME: ClassVar[str] = 'Ethernet Segment'
    SHORT_NAME: ClassVar[str] = 'Segment'

    def __init__(
        self,
        packed: Buffer,
        action: Action,
        addpath: Any = None,
        nexthop: IP = IP.NoNextHop,
    ) -> None:
        EVPN.__init__(self, action, addpath)
        self._packed = packed
        self.nexthop = nexthop

    @classmethod
    def make_ethernetsegment(
        cls,
        rd: RouteDistinguisher,
        esi: ESI,
        ip: IP,
        nexthop: IP = IP.NoNextHop,
        action: Action | None = None,
        addpath: Any = None,
    ) -> 'EthernetSegment':
        """Factory method to create EthernetSegment from semantic parameters."""
        packed = bytes(rd.pack_rd()) + esi.pack_esi() + bytes([len(ip) * 8]) + ip.pack_ip()
        return cls(packed, nexthop, action, addpath)

    @property
    def rd(self) -> RouteDistinguisher:
        return RouteDistinguisher.unpack_routedistinguisher(self._packed[:8])

    @property
    def esi(self) -> ESI:
        return ESI.unpack_esi(self._packed[8:18])

    @property
    def ip(self) -> IP:
        iplen = self._packed[18]
        return IP.unpack_ip(self._packed[19 : 19 + (iplen // 8)])

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

    @classmethod
    def unpack_evpn(cls, data: Buffer) -> EVPN:
        iplen = data[18]

        if iplen not in (32, 128):
            raise Notify(
                3,
                5,
                'IP length field is given as %d in current Segment, expecting 32 (IPv4) or 128 (IPv6) bits' % iplen,
            )

        return cls(data)

    def json(self, compact: bool | None = None) -> str:
        content = ' "code": %d, ' % self.CODE
        content += '"parsed": true, '
        content += '"raw": "{}", '.format(self._raw())
        content += '"name": "{}", '.format(self.NAME)
        content += '{}, '.format(self.rd.json())
        content += self.esi.json()
        content += ', "ip": "{}"'.format(str(self.ip))
        return '{{{} }}'.format(content)
