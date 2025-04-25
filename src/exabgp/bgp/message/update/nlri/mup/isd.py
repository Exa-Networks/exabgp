"""
isd.py

Created by Takeru Hayasaka on 2023-01-21.
Copyright (c) 2023 BBSakura Networks Inc. All rights reserved.
"""

from __future__ import annotations

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
    NAME = 'InterworkSegmentDiscoveryRoute'
    SHORT_NAME = 'ISD'

    def __init__(self, rd, prefix_ip_len, prefix_ip, afi, packed=None):
        MUP.__init__(self, afi)
        self.rd = rd
        self.prefix_ip_len = prefix_ip_len
        self.prefix_ip = prefix_ip
        self._pack(packed)

    def index(self):
        return MUP.index(self)

    def __eq__(self, other):
        return (
            isinstance(other, InterworkSegmentDiscoveryRoute)
            and self.rd == other.rd
            and self.prefix_ip_len == other.prefix_ip_len
            and self.prefix_ip == other.prefix_ip
        )

    def __ne__(self, other):
        return not self.__eq__(other)

    def __str__(self):
        return '%s:%s:%s%s' % (self._prefix(), self.rd._str(), self.prefix_ip, '/%d' % self.prefix_ip_len)

    def __hash__(self):
        return hash((self.rd, self.prefix_ip_len, self.prefix_ip))

    def _pack(self, packed=None):
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
        )
        # fmt: on
        return self._packed

    @classmethod
    def unpack(cls, data, afi):
        rd = RouteDistinguisher.unpack(data[:8])
        prefix_ip_len = data[8]
        size = 4 if afi != AFI.ipv6 else 16
        ip = data[9:]
        padding = size - len(ip)
        if padding != 0 and 0 < padding:
            ip += bytes(padding)
        prefix_ip = IP.unpack(ip)

        return cls(rd, prefix_ip_len, prefix_ip, afi)

    def json(self, compact=None):
        content = '"name": "%s", ' % self.NAME
        content += '"arch": %d, ' % self.ARCHTYPE
        content += '"code": %d, ' % self.CODE
        content += '"prefix_ip_len": %d, ' % self.prefix_ip_len
        content += '"prefix_ip": "%s", ' % str(self.prefix_ip)
        content += self.rd.json()
        content += ', "raw": "%s"' % self._raw()
        return '{ %s }' % content
