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

    def __init__(
        self,
        rd: RouteDistinguisher,
        endpoint_len: int,
        endpoint_ip: IP,
        teid: int,
        afi: AFI,
        packed: bytes | None = None,
    ) -> None:
        MUP.__init__(self, afi)
        self.rd: RouteDistinguisher = rd
        self.endpoint_len: int = endpoint_len
        self.endpoint_ip: IP = endpoint_ip
        self.teid: int = teid
        self._pack(packed)

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

    def _pack(self, packed: bytes | None = None) -> bytes:
        if self._packed:
            return self._packed

        if packed:
            self._packed = packed
            return packed

        # fmt: off
        self._packed = (
            self.rd.pack_rd()
            + pack('!B', self.endpoint_len)
            + self.endpoint_ip.pack_ip()
        )
        # fmt: on

        endpoint_size = MUP_T2ST_IPV4_SIZE_BITS if self.endpoint_ip.afi == AFI.ipv4 else MUP_T2ST_IPV6_SIZE_BITS
        teid_size = self.endpoint_len - endpoint_size

        if teid_size < 0 or teid_size > MUP_T2ST_TEID_MAX_SIZE:
            raise Exception('teid is too large %d (range 0~32)' % teid_size)

        teid_packed = pack('!I', self.teid)

        offset = teid_size // 8
        remainder = teid_size % 8
        if remainder != 0:
            offset += 1

        # as the fix is part of a large patch ..
        # this is where the main problem was: taking wrong bits
        if teid_size > 0:
            self._packed += teid_packed[-offset:]

        return self._packed

    @classmethod
    def unpack_mup_route(cls, data: bytes, afi: AFI) -> Type2SessionTransformedRoute:
        afi_bit_size = MUP_T2ST_IPV4_SIZE_BITS if afi == AFI.ipv4 else MUP_T2ST_IPV6_SIZE_BITS
        afi_bytes_size = 4 if afi == AFI.ipv4 else 16
        rd = RouteDistinguisher.unpack_routedistinguisher(data[:8])
        endpoint_len = data[8]
        end = 9 + afi_bytes_size
        endpoint_ip = IP.unpack_ip(data[9:end])

        teid = 0
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

            teid = int.from_bytes(data[end:], 'big')

        return cls(rd, endpoint_len, endpoint_ip, teid, afi)

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
