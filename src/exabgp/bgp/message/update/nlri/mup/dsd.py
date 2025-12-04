"""dsd.py

Created by Takeru Hayasaka on 2023-01-21.
Copyright (c) 2023 BBSakura Networks Inc. All rights reserved.
"""

from __future__ import annotations

from typing import Any, ClassVar
from exabgp.protocol.ip import IP
from exabgp.bgp.message.update.nlri.qualifier import RouteDistinguisher
from exabgp.protocol.family import AFI

from exabgp.bgp.message.update.nlri.mup.nlri import MUP

from exabgp.bgp.message.notification import Notify


# +-----------------------------------+
# |           RD  (8 octets)          |
# +-----------------------------------+
# |        Address (4 or 16 octets)   |
# +-----------------------------------+


@MUP.register
class DirectSegmentDiscoveryRoute(MUP):
    ARCHTYPE: ClassVar[int] = 1
    CODE: ClassVar[int] = 2
    NAME: ClassVar[str] = 'DirectSegmentDiscoveryRoute'
    SHORT_NAME: ClassVar[str] = 'DSD'

    def __init__(self, packed: bytes, afi: AFI) -> None:
        MUP.__init__(self, afi)
        self._packed = packed

    @classmethod
    def make_dsd(
        cls,
        rd: RouteDistinguisher,
        ip: IP,
        afi: AFI,
    ) -> 'DirectSegmentDiscoveryRoute':
        """Factory method to create DSD from semantic parameters."""
        packed = rd.pack_rd() + ip.pack_ip()
        return cls(packed, afi)

    @property
    def rd(self) -> RouteDistinguisher:
        return RouteDistinguisher.unpack_routedistinguisher(self._packed[:8])

    @property
    def ip(self) -> IP:
        data_len = len(self._packed)
        size = data_len - 8
        return IP.unpack_ip(self._packed[8 : 8 + size])

    def index(self) -> bytes:
        return MUP.index(self)

    def __eq__(self, other: Any) -> bool:
        return isinstance(other, DirectSegmentDiscoveryRoute) and self.rd == other.rd and self.ip == other.ip

    def __ne__(self, other: Any) -> bool:
        return not self.__eq__(other)

    def __str__(self) -> str:
        return '{}:{}:{}'.format(
            self._prefix(),
            self.rd._str(),
            self.ip,
        )

    def __hash__(self) -> int:
        return hash((self.rd, self.ip))

    @classmethod
    def unpack_mup_route(cls, data: bytes, afi: AFI) -> DirectSegmentDiscoveryRoute:
        data_len = len(data)
        size = data_len - 8
        if size not in [4, 16]:
            raise Notify(3, 5, 'Invalid IP size, expect 4 or 16 octets. accuracy size %d' % size)
        return cls(data, afi)

    def json(self, compact: bool | None = None) -> str:
        content = '"name": "{}", '.format(self.NAME)
        content += '"arch": %d, ' % self.ARCHTYPE
        content += '"code": %d, ' % self.CODE
        content += '"ip": "{}", '.format(str(self.ip))
        content += self.rd.json()
        content += ', "raw": "{}"'.format(self._raw())
        return '{{ {} }}'.format(content)
