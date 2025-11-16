"""dsd.py

Created by Takeru Hayasaka on 2023-01-21.
Copyright (c) 2023 BBSakura Networks Inc. All rights reserved.
"""

from __future__ import annotations

from typing import Any, ClassVar, Optional
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

    def __init__(self, rd: RouteDistinguisher, ip: IP, afi: AFI, packed: Optional[bytes] = None) -> None:
        MUP.__init__(self, afi)
        self.rd: RouteDistinguisher = rd
        self.ip: IP = ip
        self._pack(packed)

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

    def _pack(self, packed: Optional[bytes] = None) -> bytes:
        if self._packed:
            return self._packed

        if packed:
            self._packed = packed
            return packed

        # fmt: off
        self._packed = (
            self.rd.pack_rd()
            + self.ip.pack_ip()
        )
        # fmt: on
        return self._packed

    @classmethod
    def unpack_mup_route(cls, data: bytes, afi: AFI) -> DirectSegmentDiscoveryRoute:
        data_len = len(data)
        rd = RouteDistinguisher.unpack_routedistinguisher(data[:8])
        size = data_len - 8
        if size not in [4, 16]:
            raise Notify(3, 5, 'Invalid IP size, expect 4 or 16 octets. accuracy size %d' % size)
        ip = IP.unpack_ip(data[8 : 8 + size])

        return cls(rd, ip, afi)

    def json(self, compact: Optional[bool] = None) -> str:
        content = '"name": "{}", '.format(self.NAME)
        content += '"arch": %d, ' % self.ARCHTYPE
        content += '"code": %d, ' % self.CODE
        content += '"ip": "{}", '.format(str(self.ip))
        content += self.rd.json()
        content += ', "raw": "{}"'.format(self._raw())
        return '{{ {} }}'.format(content)
