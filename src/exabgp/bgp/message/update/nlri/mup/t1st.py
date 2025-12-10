"""t1st.py

Created by Takeru Hayasaka on 2023-01-21.
Copyright (c) 2023 BBSakura Networks Inc. All rights reserved.
"""

from __future__ import annotations

from struct import pack
from typing import TYPE_CHECKING, Any, ClassVar

if TYPE_CHECKING:
    from exabgp.bgp.message.open.capability.negotiated import Negotiated

from exabgp.bgp.message import Action
from exabgp.bgp.message.update.nlri.mup.nlri import MUP
from exabgp.bgp.message.update.nlri.nlri import NLRI
from exabgp.bgp.message.update.nlri.qualifier import RouteDistinguisher
from exabgp.protocol.family import AFI, SAFI, Family
from exabgp.protocol.ip import IP
from exabgp.util.types import Buffer

# +-----------------------------------+
# |           RD  (8 octets)          |
# +-----------------------------------+
# |      Prefix Length (1 octet)      |
# +-----------------------------------+
# |         Prefix (variable)         |
# +-----------------------------------+
# | Architecture specific (variable)  |
# +-----------------------------------+

# 3gpp-5g Specific BGP Type 1 ST Route
#   +-----------------------------------+
#   |          TEID (4 octets)          |
#   +-----------------------------------+
#   |          QFI (1 octet)            |
#   +-----------------------------------+
#   | Endpoint Address Length (1 octet) |
#   +-----------------------------------+
#   |    Endpoint Address (variable)    |
#   +-----------------------------------+
#   |  Source Address Length (1 octet)  |
#   +-----------------------------------+
#   |     Source Address (variable)     |
#   +-----------------------------------+


@MUP.register_mup_route
class Type1SessionTransformedRoute(MUP):
    ARCHTYPE: ClassVar[int] = 1
    CODE: ClassVar[int] = 3
    NAME: ClassVar[str] = 'Type1SessionTransformedRoute'
    SHORT_NAME: ClassVar[str] = 'T1ST'

    # Wire format offsets (after 4-byte header: arch(1) + code(2) + length(1))
    HEADER_SIZE: ClassVar[int] = 4
    RD_OFFSET: ClassVar[int] = 4  # Bytes 4-11: RD (8 bytes)
    PREFIX_LEN_OFFSET: ClassVar[int] = 12  # Byte 12: prefix length
    PREFIX_OFFSET: ClassVar[int] = 13  # Bytes 13+: prefix (variable)

    def __init__(self, packed: Buffer, afi: AFI) -> None:
        """Create T1ST with complete wire format.

        Args:
            packed: Complete wire format including 4-byte header
        """
        MUP.__init__(self, afi)
        self._packed: Buffer = packed

    @classmethod
    def make_t1st(
        cls,
        rd: RouteDistinguisher,
        prefix_ip_len: int,
        prefix_ip: IP,
        teid: int,
        qfi: int,
        endpoint_ip_len: int,
        endpoint_ip: IP,
        source_ip_len: int,
        source_ip: IP | bytes,
        afi: AFI,
    ) -> 'Type1SessionTransformedRoute':
        """Factory method to create T1ST from semantic parameters."""
        offset = prefix_ip_len // 8
        remainder = prefix_ip_len % 8
        if remainder != 0:
            offset += 1

        prefix_ip_packed = prefix_ip.pack_ip()
        payload = (
            bytes(rd.pack_rd())
            + pack('!B', prefix_ip_len)
            + prefix_ip_packed[0:offset]
            + pack('!IB', teid, qfi)
            + pack('!B', endpoint_ip_len)
            + endpoint_ip.pack_ip()
        )

        if source_ip_len != 0:
            source_ip_packed = source_ip.pack_ip() if isinstance(source_ip, IP) else source_ip
            payload += pack('!B', source_ip_len) + source_ip_packed

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
        ip_offset = self.prefix_ip_len // 8
        ip_remainder = self.prefix_ip_len % 8
        if ip_remainder != 0:
            ip_offset += 1

        # Offset by 4-byte header: prefix at bytes 13+
        ip = self._packed[13 : 13 + ip_offset]
        ip_size = 4 if self.afi != AFI.ipv6 else 16
        ip_padding = ip_size - ip_offset
        if ip_padding > 0:
            ip = bytes(ip) + bytes(ip_padding)
        return IP.unpack_ip(ip)

    def _get_teid_qfi_offset(self) -> int:
        """Calculate offset to TEID field (includes 4-byte header)."""
        ip_offset = self.prefix_ip_len // 8
        ip_remainder = self.prefix_ip_len % 8
        if ip_remainder != 0:
            ip_offset += 1
        # 4 (header) + 8 (RD) + 1 (prefix_len) + ip_offset
        return 13 + ip_offset

    @property
    def teid(self) -> int:
        offset = self._get_teid_qfi_offset()
        return int.from_bytes(self._packed[offset : offset + 4], 'big')

    @property
    def qfi(self) -> int:
        offset = self._get_teid_qfi_offset() + 4
        return self._packed[offset]

    @property
    def endpoint_ip_len(self) -> int:
        offset = self._get_teid_qfi_offset() + 5
        return self._packed[offset]

    @property
    def endpoint_ip(self) -> IP:
        offset = self._get_teid_qfi_offset() + 6
        ep_len = self.endpoint_ip_len // 8
        return IP.unpack_ip(self._packed[offset : offset + ep_len])

    @property
    def source_ip_len(self) -> int:
        offset = self._get_teid_qfi_offset() + 6 + self.endpoint_ip_len // 8
        datasize = len(self._packed)
        source_ip_size = datasize - offset
        if source_ip_size > 0:
            return self._packed[offset]
        return 0

    @property
    def source_ip(self) -> IP | bytes:
        offset = self._get_teid_qfi_offset() + 6 + self.endpoint_ip_len // 8
        datasize = len(self._packed)
        source_ip_size = datasize - offset
        if source_ip_size > 0:
            sip_len = self._packed[offset] // 8
            return IP.unpack_ip(self._packed[offset + 1 : offset + 1 + sip_len])
        return b''

    def __eq__(self, other: Any) -> bool:
        return (
            isinstance(other, Type1SessionTransformedRoute)
            # and self.ARCHTYPE == other.ARCHTYPE
            # and self.CODE == other.CODE
            and self.rd == other.rd
            and self.prefix_ip_len == other.prefix_ip_len
            and self.prefix_ip == other.prefix_ip
            and self.teid == other.teid
            and self.qfi == other.qfi
            and self.endpoint_ip_len == other.endpoint_ip_len
            and self.endpoint_ip == other.endpoint_ip
            and self.source_ip_len == other.source_ip_len
            and self.source_ip == other.source_ip
        )

    def __ne__(self, other: Any) -> bool:
        return not self.__eq__(other)

    def __str__(self) -> str:
        s = '{}:{}:{}{}:{}:{}:{}{}'.format(
            self._prefix(),
            self.rd._str(),
            self.prefix_ip,
            '/%d' % self.prefix_ip_len,
            self.teid,
            self.qfi,
            self.endpoint_ip,
            '/%d' % self.prefix_ip_len,
        )

        if self.source_ip_len != 0 and isinstance(self.source_ip, IP):
            s += ':%s/%d' % (self.source_ip, self.source_ip_len)

        return s

    def pack_index(self) -> bytes:
        # T1ST index excludes teid, qfi, endpoint for RIB uniqueness
        # Build index-specific payload (different from full wire format)
        index_payload = bytes(self.rd.pack_rd()) + pack('!B', self.prefix_ip_len) + self.prefix_ip.pack_ip()
        return pack('!BHB', self.ARCHTYPE, self.CODE, len(index_payload)) + index_payload

    def index(self) -> bytes:
        # T1ST uses custom index (excludes teid, qfi, endpoint)
        return bytes(Family.index(self)) + self.pack_index()

    def __hash__(self) -> int:
        # Direct _packed hash - include afi since MUP supports both IPv4 and IPv6
        return hash((self.afi, self._packed))

    @classmethod
    def unpack_nlri(
        cls, afi: AFI, safi: SAFI, data: Buffer, action: Action, addpath: Any, negotiated: Negotiated
    ) -> tuple[NLRI, Buffer]:
        # Parent provides complete wire format including 4-byte header
        # Offsets: header(0-3), RD(4-11), prefix_len(12), prefix(13+)
        prefix_ip_len = data[12]
        ip_offset = prefix_ip_len // 8
        ip_remainder = prefix_ip_len % 8
        if ip_remainder != 0:
            ip_offset += 1

        size = 13 + ip_offset  # 4 (header) + 8 (RD) + 1 (prefix_len) + prefix bytes
        size += 5  # teid (4) + qfi (1)
        endpoint_ip_len = data[size]

        if endpoint_ip_len not in [32, 128]:
            raise RuntimeError('mup t1st endpoint ip length is not 32bit or 128bit, unexpect len: %d' % endpoint_ip_len)

        ep_len = endpoint_ip_len // 8
        size += 1 + ep_len

        datasize = len(data)
        source_ip_size = datasize - size

        if source_ip_size > 0:
            source_ip_len = data[size]
            if source_ip_len not in [32, 128]:
                raise RuntimeError('mup t1st source ip length is not 32bit or 128bit, unexpect len: %d' % source_ip_len)

        instance = cls(data, afi)
        instance.action = action
        return instance, b''

    def json(self, compact: bool | None = None) -> str:
        content = '"name": "{}", '.format(self.NAME)
        content += '"arch": %d, ' % self.ARCHTYPE
        content += '"code": %d, ' % self.CODE
        content += '"prefix_ip_len": %d, ' % self.prefix_ip_len
        content += '"prefix_ip": "{}", '.format(str(self.prefix_ip))
        content += '"teid": "{}", '.format(str(self.teid))
        content += '"qfi": "{}", '.format(str(self.qfi))
        content += self.rd.json() + ', '
        content += '"endpoint_ip_len": %d, ' % self.endpoint_ip_len
        content += '"endpoint_ip": "{}", '.format(str(self.endpoint_ip))
        content += '"source_ip_len": %d, ' % self.source_ip_len
        content += '"source_ip": "{}", '.format(str(self.source_ip))
        content += '"raw": "{}"'.format(self._raw())
        return '{{ {} }}'.format(content)
