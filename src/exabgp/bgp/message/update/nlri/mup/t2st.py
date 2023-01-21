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

    def __init__(self, rd, endpoint_ip_len, endpoint_ip, teid, afi, packed=None):
        MUP.__init__(self, afi)
        self.rd = rd
        self.teid = teid
        self.endpoint_ip_len = endpoint_ip_len
        self.endpoint_ip = endpoint_ip
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
            and self.endpoint_ip_len == other.endpoint_ip_len
            and self.endpoint_ip == other.endpoint_ip
        )

    def __ne__(self, other):
        return not self.__eq__(other)

    def __str__(self):
        return "%s:%s:%s:%s:%s" % (
            self._prefix(),
            self.rd._str(),
            self.teid,
            self.endpoint_ip_len,
            self.endpoint_ip,
        )

    def __hash__(self):
        return hash(
            (
                self.rd,
                self.teid,
                self.endpoint_ip_len,
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
            + pack('!B',self.endpoint_ip_len)
            + self.endpoint_ip.pack()
            + pack('!I',self.teid)
        )
        # fmt: on
        return self._packed

    @classmethod
    def unpack(cls, data, afi):
        rd = RouteDistinguisher.unpack(data[:8])
        size = 4 if afi != AFI.ipv6 else 16
        endpoint_ip_len = data[8]
        endpoint_ip = IP.unpack(data[9: 9 + size])
        size += 9
        teid = int.from_bytes(data[size: ], "big")

        return cls(rd, endpoint_ip_len, endpoint_ip, teid, afi)

    def json(self, compact=None):
        content = ' "arch": %d, ' % self.ARCHTYPE
        content += '"code": %d, ' % self.CODE
        content += '"parsed": true, '
        content += '"raw": "%s", ' % self._raw()
        content += '"name": "%s", ' % self.NAME
        content += '%s, ' % self.rd.json()
        content += '"endpoint_ip len"%d, ' % self.endpoint_ip_len
        content += '"endpoint_ip": "%s"' % str(self.endpoint_ip)
        content += '"teid": "%s"' % str(self.teid)
        return '{%s }' % content
