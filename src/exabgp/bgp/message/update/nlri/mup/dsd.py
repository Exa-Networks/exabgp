"""dsd.py

Created by Takeru Hayasaka on 2023-01-21.
Copyright (c) 2023 BBSakura Networks Inc. All rights reserved.
"""

from __future__ import annotations

from struct import pack
from typing import TYPE_CHECKING, Any, ClassVar

from exabgp.util.types import Buffer

if TYPE_CHECKING:
    from exabgp.bgp.message.open.capability.negotiated import Negotiated

from exabgp.bgp.message import Action
from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.update.nlri.mup.nlri import MUP
from exabgp.bgp.message.update.nlri.nlri import NLRI
from exabgp.bgp.message.update.nlri.qualifier import RouteDistinguisher
from exabgp.protocol.family import AFI, SAFI
from exabgp.protocol.ip import IP

# +-----------------------------------+
# |           RD  (8 octets)          |
# +-----------------------------------+
# |        Address (4 or 16 octets)   |
# +-----------------------------------+


@MUP.register_mup_route
class DirectSegmentDiscoveryRoute(MUP):
    ARCHTYPE: ClassVar[int] = 1
    CODE: ClassVar[int] = 2
    NAME: ClassVar[str] = 'DirectSegmentDiscoveryRoute'
    SHORT_NAME: ClassVar[str] = 'DSD'

    # Wire format offsets (after 4-byte header: arch(1) + code(2) + length(1))
    HEADER_SIZE: ClassVar[int] = 4
    RD_OFFSET: ClassVar[int] = 4  # Bytes 4-11: RD (8 bytes)
    IP_OFFSET: ClassVar[int] = 12  # Bytes 12+: IP address

    def __init__(self, packed: Buffer, afi: AFI) -> None:
        """Create DSD with complete wire format.

        Args:
            packed: Complete wire format including 4-byte header
        """
        MUP.__init__(self, afi)
        self._packed: Buffer = packed

    @classmethod
    def make_dsd(
        cls,
        rd: RouteDistinguisher,
        ip: IP,
        afi: AFI,
    ) -> 'DirectSegmentDiscoveryRoute':
        """Factory method to create DSD from semantic parameters."""
        payload = bytes(rd.pack_rd()) + ip.pack_ip()
        # Include 4-byte header: arch(1) + code(2) + length(1) + payload
        packed = pack('!BHB', cls.ARCHTYPE, cls.CODE, len(payload)) + payload
        return cls(packed, afi)

    @property
    def rd(self) -> RouteDistinguisher:
        # Offset by 4-byte header: RD at bytes 4-11
        return RouteDistinguisher.unpack_routedistinguisher(self._packed[4:12])

    @property
    def ip(self) -> IP:
        # Offset by 4-byte header: IP at bytes 12+
        data_len = len(self._packed)
        size = data_len - 12  # Subtract header(4) + RD(8)
        return IP.unpack_ip(self._packed[12 : 12 + size])

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
        # Direct _packed hash - include afi since MUP supports both IPv4 and IPv6
        return hash((self.afi, self._packed))

    @classmethod
    def unpack_nlri(
        cls, afi: AFI, safi: SAFI, data: Buffer, action: Action, addpath: Any, negotiated: Negotiated
    ) -> tuple[NLRI, Buffer]:
        # Parent provides complete wire format including 4-byte header
        data_len = len(data)
        ip_size = data_len - 12  # IP is after 4-byte header + 8-byte RD
        if ip_size not in [4, 16]:
            raise Notify(3, 5, 'Invalid IP size, expect 4 or 16 octets. got %d' % ip_size)
        instance = cls(data, afi)
        return instance, b''

    def json(self, compact: bool | None = None) -> str:
        content = '"name": "{}", '.format(self.NAME)
        content += '"arch": %d, ' % self.ARCHTYPE
        content += '"code": %d, ' % self.CODE
        content += '"ip": "{}", '.format(str(self.ip))
        content += self.rd.json()
        content += ', "raw": "{}"'.format(self._raw())
        return '{{ {} }}'.format(content)
