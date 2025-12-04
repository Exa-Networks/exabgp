"""t2st.py

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

# https://datatracker.ietf.org/doc/html/draft-mpmz-bess-mup-safi-03

# +-----------------------------------+
# |           RD  (8 octets)          |
# +-----------------------------------+
# |      Endpoint Length (1 octet)    |
# +-----------------------------------+
# |      Endpoint Address (variable)  |
# +-----------------------------------+
# | Architecture specific Endpoint    |
# |         Identifier (variable)     |
# +-----------------------------------+

# 3gpp-5g Specific BGP Type 2 ST Route
# +-----------------------------------+
# |          TEID (0-4 octets)        |
# +-----------------------------------+

# MUP Type 2 Session Transformed Route constants
MUP_T2ST_IPV4_SIZE_BITS: int = 32  # IPv4 address size in bits
MUP_T2ST_IPV6_SIZE_BITS: int = 128  # IPv6 address size in bits
MUP_T2ST_TEID_MAX_SIZE: int = 32  # Maximum TEID size in bits
MUP_T2ST_IPV4_MAX_ENDPOINT: int = 64  # Max endpoint length for IPv4 (32 IP + 32 TEID)
MUP_T2ST_IPV6_MAX_ENDPOINT: int = 160  # Max endpoint length for IPv6 (128 IP + 32 TEID)


@MUP.register
class Type2SessionTransformedRoute(MUP):
    ARCHTYPE: ClassVar[int] = 1
    CODE: ClassVar[int] = 4
    NAME: ClassVar[str] = 'Type2SessionTransformedRoute'
    SHORT_NAME: ClassVar[str] = 'T2ST'

    def __init__(self, packed: bytes, afi: AFI) -> None:
        MUP.__init__(self, afi)
        self._packed = packed

    @classmethod
    def make_t2st(
        cls,
        rd: RouteDistinguisher,
        endpoint_len: int,
        endpoint_ip: IP,
        teid: int,
        afi: AFI,
    ) -> 'Type2SessionTransformedRoute':
        """Factory method to create T2ST from semantic parameters."""
        packed = rd.pack_rd() + pack('!B', endpoint_len) + endpoint_ip.pack_ip()

        endpoint_size = MUP_T2ST_IPV4_SIZE_BITS if endpoint_ip.afi == AFI.ipv4 else MUP_T2ST_IPV6_SIZE_BITS
        teid_size = endpoint_len - endpoint_size

        if teid_size < 0 or teid_size > MUP_T2ST_TEID_MAX_SIZE:
            raise Exception('teid is too large %d (range 0~32)' % teid_size)

        teid_packed = pack('!I', teid)

        offset = teid_size // 8
        remainder = teid_size % 8
        if remainder != 0:
            offset += 1

        if teid_size > 0:
            packed += teid_packed[-offset:]

        return cls(packed, afi)

    @property
    def rd(self) -> RouteDistinguisher:
        return RouteDistinguisher.unpack_routedistinguisher(self._packed[:8])

    @property
    def endpoint_len(self) -> int:
        return self._packed[8]

    @property
    def endpoint_ip(self) -> IP:
        afi_bytes_size = 4 if self.afi == AFI.ipv4 else 16
        return IP.unpack_ip(self._packed[9 : 9 + afi_bytes_size])

    @property
    def teid(self) -> int:
        afi_bit_size = MUP_T2ST_IPV4_SIZE_BITS if self.afi == AFI.ipv4 else MUP_T2ST_IPV6_SIZE_BITS
        afi_bytes_size = 4 if self.afi == AFI.ipv4 else 16
        end = 9 + afi_bytes_size
        if self.endpoint_len > afi_bit_size:
            return int.from_bytes(self._packed[end:], 'big')
        return 0

    def index(self) -> bytes:
        return MUP.index(self)

    def __eq__(self, other: Any) -> bool:
        return (
            isinstance(other, Type2SessionTransformedRoute)
            and self.rd == other.rd
            and self.teid == other.teid
            and self.endpoint_len == self.endpoint_len
            and self.endpoint_ip == other.endpoint_ip
        )

    def __ne__(self, other: Any) -> bool:
        return not self.__eq__(other)

    def __str__(self) -> str:
        return '{}:{}:{}:{}:{}:'.format(
            self._prefix(),
            self.rd._str(),
            self.endpoint_len,
            self.endpoint_ip,
            self.teid,
        )

    def __hash__(self) -> int:
        return hash(
            (
                self.rd,
                self.teid,
                self.endpoint_len,
                self.endpoint_ip,
            ),
        )

    @classmethod
    def unpack_mup_route(cls, data: bytes, afi: AFI) -> Type2SessionTransformedRoute:
        afi_bit_size = MUP_T2ST_IPV4_SIZE_BITS if afi == AFI.ipv4 else MUP_T2ST_IPV6_SIZE_BITS
        endpoint_len = data[8]

        if endpoint_len > afi_bit_size:
            teid_len = endpoint_len - afi_bit_size
            if afi == AFI.ipv4 and teid_len > MUP_T2ST_TEID_MAX_SIZE:
                raise Exception(
                    'endpoint length is too large %d (max %d for Ipv4)' % (endpoint_len, MUP_T2ST_IPV4_MAX_ENDPOINT)
                )
            if afi == AFI.ipv6 and teid_len > MUP_T2ST_TEID_MAX_SIZE:
                raise Exception(
                    'endpoint length is too large %d (max %d for Ipv6)' % (endpoint_len, MUP_T2ST_IPV6_MAX_ENDPOINT)
                )

        return cls(data, afi)

    def json(self, compact: bool | None = None) -> str:
        content = '"name": "{}", '.format(self.NAME)
        content += ' "arch": %d, ' % self.ARCHTYPE
        content += '"code": %d, ' % self.CODE
        content += '"endpoint_len": %d, ' % self.endpoint_len
        content += '"endpoint_ip": "{}", '.format(str(self.endpoint_ip))
        content += self.rd.json() + ', '
        content += '"teid": "{}", '.format(str(self.teid))
        content += '"raw": "{}"'.format(self._raw())
        return '{{ {} }}'.format(content)
