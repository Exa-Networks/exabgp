"""
t2st.py

Created by Takeru Hayasaka on 2023-01-21.
Copyright (c) 2023 BBSakura Networks Inc. All rights reserved.
"""

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


@MUP.register
class Type2SessionTransformedRoute(MUP):
    ARCHTYPE = 1
    CODE = 4
    NAME = 'Type2SessionTransformedRoute'
    SHORT_NAME = 'T2ST'

    def __init__(self, rd, endpoint_len, endpoint_ip, teid, afi, packed=None):
        MUP.__init__(self, afi)
        self.rd = rd
        self.endpoint_len = endpoint_len
        self.endpoint_ip = endpoint_ip
        self.teid = teid
        self._pack(packed)

    def index(self):
        return MUP.index(self)

    def __eq__(self, other):
        return (
            isinstance(other, Type2SessionTransformedRoute)
            and self.rd == other.rd
            and self.teid == other.teid
            and self.endpoint_len == self.endpoint_len
            and self.endpoint_ip == other.endpoint_ip
        )

    def __ne__(self, other):
        return not self.__eq__(other)

    def __str__(self):
        return '%s:%s:%s:%s:%s:' % (
            self._prefix(),
            self.rd._str(),
            self.endpoint_len,
            self.endpoint_ip,
            self.teid,
        )

    def __hash__(self):
        return hash(
            (
                self.rd,
                self.teid,
                self.endpoint_len,
                self.endpoint_ip,
            )
        )

    def _pack(self, packed=None):
        if self._packed:
            return self._packed

        if packed:
            self._packed = packed
            return packed

        # fmt: off
        self._packed = (
            self.rd.pack()
            + pack('!B', self.endpoint_len)
            + self.endpoint_ip.pack()
        )
        # fmt: on

        endpoint_size = 32 if self.endpoint_ip.afi == AFI.ipv4 else 128
        teid_size = self.endpoint_len - endpoint_size

        if teid_size < 0 or teid_size > 32:
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
    def unpack(cls, data, afi):
        afi_bit_size = 32 if afi == AFI.ipv4 else 128
        afi_bytes_size = 4 if afi == AFI.ipv4 else 16
        rd = RouteDistinguisher.unpack(data[:8])
        endpoint_len = data[8]
        end = 9 + afi_bytes_size
        endpoint_ip = IP.unpack(data[9:end])

        teid = 0
        if endpoint_len > afi_bit_size:
            teid_len = endpoint_len - afi_bit_size
            if afi == AFI.ipv4 and teid_len > 32:
                raise Exception('endpoint length is too large %d (max 64 for Ipv4)' % endpoint_len)
            if afi == AFI.ipv6 and teid_len > 32:
                raise Exception('endpoint length is too large %d (max 160 for Ipv6)' % endpoint_len)

            teid = int.from_bytes(data[end:], 'big')

        return cls(rd, endpoint_len, endpoint_ip, teid, afi)

    def json(self, compact=None):
        content = '"name": "%s", ' % self.NAME
        content += ' "arch": %d, ' % self.ARCHTYPE
        content += '"code": %d, ' % self.CODE
        content += '"endpoint_len": %d, ' % self.endpoint_len
        content += '"endpoint_ip": "%s", ' % str(self.endpoint_ip)
        content += self.rd.json() + ', '
        content += '"teid": "%s", ' % str(self.teid)
        content += '"raw": "%s"' % self._raw()
        return '{ %s }' % content
