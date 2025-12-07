"""segment.py

Created by Thomas Mangin on 2014-06-27.
Copyright (c) 2014-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from typing import ClassVar

from exabgp.bgp.message import Action
from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.update.nlri.evpn.nlri import EVPN
from exabgp.bgp.message.update.nlri.qualifier import ESI, RouteDistinguisher
from exabgp.bgp.message.update.nlri.qualifier.path import PathInfo
from exabgp.protocol.ip import IP

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
    """EVPN Route Type 4: Ethernet Segment.

    Wire format: type(1) + length(1) + RD(8) + ESI(10) + IPlen(1) + IP(4/16)
    Uses packed-bytes-first pattern for zero-copy routing.
    """

    CODE: ClassVar[int] = 4
    NAME: ClassVar[str] = 'Ethernet Segment'
    SHORT_NAME: ClassVar[str] = 'Segment'

    def __init__(self, packed: bytes) -> None:
        """Create EthernetSegment from complete wire-format bytes.

        Args:
            packed: Complete wire format (type + length + payload)
        """
        EVPN.__init__(self, packed)

    @classmethod
    def make_ethernetsegment(
        cls,
        rd: RouteDistinguisher,
        esi: ESI,
        ip: IP,
        action: Action = Action.UNSET,
        addpath: PathInfo = PathInfo.DISABLED,
    ) -> 'EthernetSegment':
        """Factory method to create EthernetSegment from semantic parameters.

        Packs fields into wire format immediately (packed-bytes-first pattern).
        Note: nexthop is not part of NLRI - set separately after creation.
        """
        payload = bytes(rd.pack_rd()) + esi.pack_esi() + bytes([len(ip) * 8]) + ip.pack_ip()
        # Include type + length header for zero-copy pack
        packed = bytes([cls.CODE, len(payload)]) + payload
        instance = cls(packed)
        instance.action = action
        instance.addpath = addpath
        return instance

    # Wire format offsets (after 2-byte type+length header):
    # RD: 2-10, ESI: 10-20, IPlen: 20, IP: 21+

    @property
    def rd(self) -> RouteDistinguisher:
        """Route Distinguisher - unpacked from wire bytes."""
        return RouteDistinguisher.unpack_routedistinguisher(self._packed[2:10])

    @property
    def esi(self) -> ESI:
        """Ethernet Segment Identifier - unpacked from wire bytes."""
        return ESI.unpack_esi(self._packed[10:20])

    @property
    def ip(self) -> IP:
        """Originating Router IP - unpacked from wire bytes."""
        iplen = self._packed[20]
        return IP.unpack_ip(self._packed[21 : 21 + (iplen // 8)])

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
    def unpack_evpn(cls, packed: bytes) -> EVPN:
        """Unpack EthernetSegment from complete wire format bytes.

        Args:
            packed: Complete wire format (type + length + payload)

        Returns:
            EthernetSegment instance with stored wire bytes
        """
        # IPlen is at offset 20 (after 2-byte header + 8-byte RD + 10-byte ESI)
        iplen = packed[20]

        if iplen not in (32, 128):
            raise Notify(
                3,
                5,
                'IP length field is given as %d in current Segment, expecting 32 (IPv4) or 128 (IPv6) bits' % iplen,
            )

        return cls(packed)

    def json(self, compact: bool | None = None) -> str:
        content = ' "code": %d, ' % self.CODE
        content += '"parsed": true, '
        content += '"raw": "{}", '.format(self._raw())
        content += '"name": "{}", '.format(self.NAME)
        content += '{}, '.format(self.rd.json())
        content += self.esi.json()
        content += ', "ip": "{}"'.format(str(self.ip))
        return '{{{} }}'.format(content)
