"""isd.py

Created by Takeru Hayasaka on 2023-01-21.
Copyright (c) 2023 BBSakura Networks Inc. All rights reserved.
"""

from __future__ import annotations

from typing import Any, ClassVar
from exabgp.protocol.ip import IP
from exabgp.bgp.message.update.nlri.qualifier import RouteDistinguisher
from exabgp.protocol.family import AFI

from exabgp.bgp.message.update.nlri.mup.nlri import MUP

from struct import pack


# +-----------------------------------+
# |           RD  (8 octets)          |
# +-----------------------------------+
# |       Prefix Length (1 octet)     |
# +-----------------------------------+
# |        Prefix (variable)          |
# +-----------------------------------+


@MUP.register
class InterworkSegmentDiscoveryRoute(MUP):
    ARCHTYPE: ClassVar[int] = 1
    CODE: ClassVar[int] = 1
    NAME: ClassVar[str] = 'InterworkSegmentDiscoveryRoute'
    SHORT_NAME: ClassVar[str] = 'ISD'

    def __init__(self, packed: bytes, afi: AFI) -> None:
        MUP.__init__(self, afi)
        self._packed = packed

    @classmethod
    def make_isd(
        cls,
        rd: RouteDistinguisher,
        prefix_ip_len: int,
        prefix_ip: IP,
        afi: AFI,
    ) -> 'InterworkSegmentDiscoveryRoute':
        """Factory method to create ISD from semantic parameters."""
        offset = prefix_ip_len // 8
        remainder = prefix_ip_len % 8
        if remainder != 0:
            offset += 1

        prefix_ip_packed = prefix_ip.pack_ip()
        packed = rd.pack_rd() + pack('!B', prefix_ip_len) + prefix_ip_packed[0:offset]
        return cls(packed, afi)

    @property
    def rd(self) -> RouteDistinguisher:
        return RouteDistinguisher.unpack_routedistinguisher(self._packed[:8])

    @property
    def prefix_ip_len(self) -> int:
        return self._packed[8]

    @property
    def prefix_ip(self) -> IP:
        size = 4 if self.afi != AFI.ipv6 else 16
        ip = self._packed[9:]
        padding = size - len(ip)
        if padding > 0:
            ip = ip + bytes(padding)
        return IP.unpack_ip(ip)

    def index(self) -> bytes:
        return MUP.index(self)

    def __eq__(self, other: Any) -> bool:
        return (
            isinstance(other, InterworkSegmentDiscoveryRoute)
            and self.rd == other.rd
            and self.prefix_ip_len == other.prefix_ip_len
            and self.prefix_ip == other.prefix_ip
        )

    def __ne__(self, other: Any) -> bool:
        return not self.__eq__(other)

    def __str__(self) -> str:
        return '{}:{}:{}{}'.format(self._prefix(), self.rd._str(), self.prefix_ip, '/%d' % self.prefix_ip_len)

    def __hash__(self) -> int:
        return hash((self.rd, self.prefix_ip_len, self.prefix_ip))

    @classmethod
    def unpack_mup_route(cls, data: bytes, afi: AFI) -> InterworkSegmentDiscoveryRoute:
        return cls(data, afi)

    def json(self, compact: bool | None = None) -> str:
        content = '"name": "{}", '.format(self.NAME)
        content += '"arch": %d, ' % self.ARCHTYPE
        content += '"code": %d, ' % self.CODE
        content += '"prefix_ip_len": %d, ' % self.prefix_ip_len
        content += '"prefix_ip": "{}", '.format(str(self.prefix_ip))
        content += self.rd.json()
        content += ', "raw": "{}"'.format(self._raw())
        return '{{ {} }}'.format(content)
