"""t1st.py

Created by Takeru Hayasaka on 2023-01-21.
Copyright (c) 2023 BBSakura Networks Inc. All rights reserved.
"""

from __future__ import annotations

from typing import Any, ClassVar, Optional, Union
from exabgp.protocol.ip import IP
from exabgp.bgp.message.update.nlri.qualifier import RouteDistinguisher
from exabgp.protocol.family import AFI
from exabgp.protocol.family import Family

from exabgp.bgp.message.update.nlri.mup.nlri import MUP
from struct import pack


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


@MUP.register
class Type1SessionTransformedRoute(MUP):
    ARCHTYPE: ClassVar[int] = 1
    CODE: ClassVar[int] = 3
    NAME: ClassVar[str] = 'Type1SessionTransformedRoute'
    SHORT_NAME: ClassVar[str] = 'T1ST'

    def __init__(
        self,
        rd: RouteDistinguisher,
        prefix_ip_len: int,
        prefix_ip: IP,
        teid: int,
        qfi: int,
        endpoint_ip_len: int,
        endpoint_ip: IP,
        source_ip_len: int,
        source_ip: Union[IP, bytes],
        afi: AFI,
        packed: Optional[bytes] = None,
    ) -> None:
        MUP.__init__(self, afi)
        self.rd: RouteDistinguisher = rd
        self.prefix_ip_len: int = prefix_ip_len
        self.prefix_ip: IP = prefix_ip
        self.teid: int = teid
        self.qfi: int = qfi
        self.endpoint_ip_len: int = endpoint_ip_len
        self.endpoint_ip: IP = endpoint_ip
        self.source_ip_len: int = source_ip_len
        self.source_ip: Union[IP, bytes] = source_ip
        self._pack(packed)

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

        if self.source_ip_len != 0 and self.source_ip != b'':
            s += ':%s/%d' % (self.source_ip, self.source_ip_len)

        return s

    def pack_index(self) -> bytes:
        # removed teid, qfi, endpointip
        packed = self.rd.pack() + pack('!B', self.prefix_ip_len) + self.prefix_ip.pack()
        return pack('!BHB', self.ARCHTYPE, self.CODE, len(packed)) + packed

    def index(self) -> bytes:
        return Family.index(self) + self.pack_index()

    def __hash__(self) -> int:
        return hash(
            (
                self.rd,
                self.prefix_ip_len,
                self.prefix_ip,
                self.teid,
                self.qfi,
                self.endpoint_ip_len,
                self.endpoint_ip,
                self.source_ip_len,
                self.source_ip,
            ),
        )

    def _pack(self, packed: Optional[bytes] = None) -> bytes:
        if self._packed:
            return self._packed

        if packed:
            self._packed = packed
            return packed

        offset = self.prefix_ip_len // 8
        remainder = self.prefix_ip_len % 8
        if remainder != 0:
            offset += 1

        prefix_ip_packed = self.prefix_ip.pack()

        # fmt: off
        self._packed = (
            self.rd.pack()
            + pack('!B',self.prefix_ip_len)
            + prefix_ip_packed[0: offset]
            + pack('!IB',self.teid, self.qfi)
            + pack('!B',self.endpoint_ip_len)
            + self.endpoint_ip.pack()
        )

        if self.source_ip_len != 0:
            source_ip_packed = self.source_ip.pack() if isinstance(self.source_ip, IP) else self.source_ip
            self._packed += pack('!B', self.source_ip_len) + source_ip_packed

        # fmt: on
        return self._packed

    @classmethod
    def unpack(cls, data: bytes, afi: AFI) -> Type1SessionTransformedRoute:
        datasize = len(data)
        rd = RouteDistinguisher.unpack(data[:8])
        prefix_ip_len = data[8]
        ip_offset = prefix_ip_len // 8
        ip_remainder = prefix_ip_len % 8
        if ip_remainder != 0:
            ip_offset += 1

        ip = data[9 : 9 + ip_offset]
        ip_size = 4 if afi != AFI.ipv6 else 16
        ip_padding = ip_size - ip_offset
        if ip_padding != 0 and ip_padding > 0:
            ip += bytes(ip_padding)

        size = ip_offset
        prefix_ip = IP.unpack(ip)
        size += 9
        teid = int.from_bytes(data[size : size + 4], 'big')
        size += 4
        qfi = data[size]
        size += 1
        endpoint_ip_len = data[size]
        size += 1

        if endpoint_ip_len not in [32, 128]:
            raise RuntimeError('mup t1st endpoint ip length is not 32bit or 128bit, unexpect len: %d' % endpoint_ip_len)

        ep_len = endpoint_ip_len // 8
        endpoint_ip = IP.unpack(data[size : size + ep_len])
        size += ep_len

        source_ip_size = datasize - size

        source_ip_len = 0
        source_ip: Union[IP, bytes] = b''

        if source_ip_size > 0:
            source_ip_len = data[size]
            size += 1
            if source_ip_len not in [32, 128]:
                raise RuntimeError('mup t1st source ip length is not 32bit or 128bit, unexpect len: %d' % source_ip_len)
            sip_len = source_ip_len // 8
            source_ip = IP.unpack(data[size : size + sip_len])
            size += sip_len

        return cls(rd, prefix_ip_len, prefix_ip, teid, qfi, endpoint_ip_len, endpoint_ip, source_ip_len, source_ip, afi)

    def json(self, compact: Optional[bool] = None) -> str:
        content = '"name": "{}", '.format(self.NAME)
        content += '"arch": %d, ' % self.ARCHTYPE
        content += '"code": %d, ' % self.CODE
        content += '"prefix_ip_len": %d, ' % self.prefix_ip_len
        content += '"prefix_ip": "{}", '.format(str(self.prefix_ip))
        content += '"teid": "{}", '.format(str(self.teid))
        content += '"qfi": "{}", '.format(str(self.qfi))
        content += self.rd.json() + ', '
        content += '"endpoint_ip_len": %d, ' % self.endpoint_ip_len
        content += '"endpoint_ip": "{}"'.format(str(self.endpoint_ip))
        content += '"source_ip_len": %d, ' % self.source_ip_len
        content += '"source_ip": "{}", '.format(str(self.source_ip))
        content += '"raw": "{}"'.format(self._raw())
        return '{{ {} }}'.format(content)
