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
    NAME = "Type2SessionTransformedRoute"
    SHORT_NAME = "T2ST"

    def __init__(self, rd, endpoint_ip_len, endpoint_ip, teid, teid_len, afi, packed=None):
        MUP.__init__(self, afi)
        self.rd = rd
        self.teid = teid
        self.teid_len = teid_len
        self.endpoint_ip = endpoint_ip
        self.endpoint_ip_len = endpoint_ip_len
        self.endpoint_len = teid_len + endpoint_ip_len
        self._pack(packed)

    def index(self):
        return MUP.index(self)

    def __eq__(self, other):
        return (
            isinstance(other, Type2SessionTransformedRoute)
            and self.ARCHTYPE == other.ARCHTYPE
            and self.CODE == other.CODE
            and self.rd == other.rd
            and self.teid == other.teid
            and self.endpoint_ip == other.endpoint_ip
            and self.endpoint_len == self.endpoint_len
        )

    def __ne__(self, other):
        return not self.__eq__(other)

    def __str__(self):
        return "%s:%s:%s:%s:%s:" % (
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

        teid_packed = pack('!I', self.teid)
        offset = self.teid_len // 8
        remainder = self.teid_len % 8
        if remainder != 0:
            offset += 1

        # fmt: off
        self._packed = (
            self.rd.pack()
            + pack('!B', self.endpoint_len)
            + self.endpoint_ip.pack()
        )
        if 0 < self.teid_len:
            self._packed += teid_packed[0: offset]
        # fmt: on
        return self._packed

    @classmethod
    def unpack(cls, data, afi):
        rd = RouteDistinguisher.unpack(data[:8])
        size = 4 if afi != AFI.ipv6 else 16
        endpoint_len = data[8]
        endpoint_ip_len = size * 8
        teid_len = endpoint_len - endpoint_ip_len
        if not (0 <= teid_len <= 32):
            raise Exception("teid len is %d, but len range 0 ~ 32" % teid_len)

        endpoint_ip = IP.unpack(data[9 : 9 + size])
        size += 9
        if 0 < teid_len:
            teid = int.from_bytes(data[size:], "big")
        else:
            teid = 0
        return cls(rd, endpoint_ip_len, endpoint_ip, teid, teid_len, afi)

    def json(self, compact=None):
        content = ' "arch": %d, ' % self.ARCHTYPE
        content += '"code": %d, ' % self.CODE
        content += '"raw": "%s", ' % self._raw()
        content += '"name": "%s", ' % self.NAME
        content += self.rd.json() + ', '
        content += '"endpoint_len": %d, ' % self.endpoint_len
        content += '"endpoint_ip": "%s", ' % str(self.endpoint_ip)
        content += '"teid": "%s"' % str(self.teid)
        return '{ %s }' % content
