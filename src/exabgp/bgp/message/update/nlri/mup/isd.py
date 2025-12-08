"""isd.py

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
from exabgp.bgp.message.update.nlri.mup.nlri import MUP
from exabgp.bgp.message.update.nlri.nlri import NLRI
from exabgp.bgp.message.update.nlri.qualifier import RouteDistinguisher
from exabgp.protocol.family import AFI, SAFI
from exabgp.protocol.ip import IP

# +-----------------------------------+
# |           RD  (8 octets)          |
# +-----------------------------------+
# |       Prefix Length (1 octet)     |
# +-----------------------------------+
# |        Prefix (variable)          |
# +-----------------------------------+


@MUP.register_mup_route
class InterworkSegmentDiscoveryRoute(MUP):
    ARCHTYPE: ClassVar[int] = 1
    CODE: ClassVar[int] = 1
    NAME: ClassVar[str] = 'InterworkSegmentDiscoveryRoute'
    SHORT_NAME: ClassVar[str] = 'ISD'

    # Wire format offsets (after 4-byte header: arch(1) + code(2) + length(1))
    HEADER_SIZE: ClassVar[int] = 4
    RD_OFFSET: ClassVar[int] = 4  # Bytes 4-11: RD (8 bytes)
    PREFIX_LEN_OFFSET: ClassVar[int] = 12  # Byte 12: prefix length
    PREFIX_OFFSET: ClassVar[int] = 13  # Bytes 13+: prefix

    def __init__(self, packed: Buffer, afi: AFI) -> None:
        """Create ISD with complete wire format.

        Args:
            packed: Complete wire format including 4-byte header
        """
        MUP.__init__(self, afi)
        self._packed: Buffer = packed

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
        payload = bytes(rd.pack_rd()) + pack('!B', prefix_ip_len) + prefix_ip_packed[0:offset]
        # Include 4-byte header: arch(1) + code(2) + length(1) + payload
        packed = pack('!BHB', cls.ARCHTYPE, cls.CODE, len(payload)) + payload
        return cls(packed, afi)

    @property
    def rd(self) -> RouteDistinguisher:
        # Offset by 4-byte header: RD at bytes 4-11
        return RouteDistinguisher.unpack_routedistinguisher(self._packed[4:12])

    @property
    def prefix_ip_len(self) -> int:
        # Offset by 4-byte header: prefix_len at byte 12
        return self._packed[12]

    @property
    def prefix_ip(self) -> IP:
        size = 4 if self.afi != AFI.ipv6 else 16
        # Offset by 4-byte header: prefix at bytes 13+
        ip = self._packed[13:]
        padding = size - len(ip)
        if padding > 0:
            ip = bytes(ip) + bytes(padding)
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
    def unpack_nlri(
        cls, afi: AFI, safi: SAFI, data: Buffer, action: Action, addpath: Any, negotiated: Negotiated
    ) -> tuple[NLRI, Buffer]:
        # Parent provides complete wire format including 4-byte header
        instance = cls(data, afi)
        instance.action = action
        return instance, b''

    def json(self, compact: bool | None = None) -> str:
        content = '"name": "{}", '.format(self.NAME)
        content += '"arch": %d, ' % self.ARCHTYPE
        content += '"code": %d, ' % self.CODE
        content += '"prefix_ip_len": %d, ' % self.prefix_ip_len
        content += '"prefix_ip": "{}", '.format(str(self.prefix_ip))
        content += self.rd.json()
        content += ', "raw": "{}"'.format(self._raw())
        return '{{ {} }}'.format(content)
