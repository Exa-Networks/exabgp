"""
isd.py

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
# |       Prefix Length (1 octet)     |
# +-----------------------------------+
# |        Prefix (variable)          |
# +-----------------------------------+


@MUP.register
class InterworkSegmentDiscoveryRoute(MUP):
    ARCHTYPE = 1
    CODE = 1
    NAME = "InterworkSegmentDiscoveryRoute"
    SHORT_NAME = "ISD"

    def __init__(self, rd, ipprefix_len, ipprefix, afi, packed=None):
        MUP.__init__(self, afi)
        self.rd = rd
        self.ipprefix_len = ipprefix_len
        self.ipprefix = ipprefix
        self._pack(packed)

    def index(self):
        return MUP.index(self)

    def __eq__(self, other):
        return (
            isinstance(other, InterworkSegmentDiscoveryRoute)
            and self.ARCHTYPE == other.ARCHTYPE
            and self.CODE == other.CODE
            and self.rd == other.rd
            and self.ipprefix_len == other.ipprefix_len
            and self.ipprefix == other.ipprefix
        )

    def __ne__(self, other):
        return not self.__eq__(other)

    def __str__(self):
        return "%s:%s:%s%s" % (self._prefix(), self.rd._str(), self.ipprefix, "/%d" % self.ipprefix_len)

    def __hash__(self):
        return hash((self.rd, self.ipprefix_len, self.ipprefix))

    def _pack(self, packed=None):
        if self._packed:
            return self._packed

        if packed:
            self._packed = packed
            return packed

        offset = self.ipprefix_len // 8
        remainder = self.ipprefix_len % 8
        if remainder != 0:
            offset += 1

        ipprefix_packed = self.ipprefix.pack()
        # fmt: off
        self._packed = (
            self.rd.pack()
            + pack('!B',self.ipprefix_len)
            + ipprefix_packed[0: offset]
        )
        # fmt: on
        return self._packed

    @classmethod
    def unpack(cls, data, afi):
        rd = RouteDistinguisher.unpack(data[:8])
        ipprefix_len = data[8]
        size = 4 if afi != AFI.ipv6 else 16
        ip = data[9:]
        padding = size - len(ip)
        if padding != 0 and 0 < padding:
            ip += bytes(padding)

        ipprefix = IP.unpack(ip)

        return cls(rd, ipprefix_len, ipprefix, afi)

    def json(self, compact=None):
        content = '"arch": %d, ' % self.ARCHTYPE
        content += '"code": %d, ' % self.CODE
        content += '"raw": "%s", ' % self._raw()
        content += '"name": "%s", ' % self.NAME
        content += self.rd.json() + ', '
        content += '"ipprefix_len": %d, ' % self.ipprefix_len
        content += '"ipprefix": "%s"' % str(self.ipprefix)
        return '{ %s }' % content
