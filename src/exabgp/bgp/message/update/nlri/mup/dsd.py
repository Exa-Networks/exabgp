"""
dsd.py

Created by Takeru Hayasaka on 2023-01-21.
Copyright (c) 2023 BBSakura Networks Inc. All rights reserved.
"""

from exabgp.protocol.ip import IP
from exabgp.bgp.message.update.nlri.qualifier import RouteDistinguisher

from exabgp.bgp.message.update.nlri.mup.nlri import MUP

from exabgp.bgp.message.notification import Notify
from struct import pack


# +-----------------------------------+
# |           RD  (8 octets)          |
# +-----------------------------------+
# |        Address (4 or 16 octets)   |
# +-----------------------------------+


@MUP.register
class DirectSegmentDiscoveryRoute(MUP):
    ARCHTYPE = 1
    CODE = 2
    NAME = "DirectSegmentDiscoveryRoute"
    SHORT_NAME = "DSD"

    def __init__(self, rd, ip, afi, packed=None):
        MUP.__init__(self, afi)
        self.rd = rd
        self.ip = ip
        self._pack(packed)

    def index(self):
        return MUP.index(self)

    def __eq__(self, other):
        return (
            isinstance(other, DirectSegmentDiscoveryRoute)
            and self.ARCHTYPE == other.ARCHTYPE
            and self.CODE == other.CODE
            and self.rd == other.rd
            and self.ip == other.ip
        )

    def __ne__(self, other):
        return not self.__eq__(other)

    def __str__(self):
        return "%s:%s:%s" % (
            self._prefix(),
            self.rd._str(),
            self.ip,
        )

    def __hash__(self):
        return hash((self.rd, self.ip))

    def _pack(self, packed=None):
        if self._packed:
            return self._packed

        if packed:
            self._packed = packed
            return packed

        # fmt: off
        self._packed = (
            self.rd.pack()
            + self.ip.pack()
        )
        # fmt: on
        return self._packed

    @classmethod
    def unpack(cls, data, afi):
        data_len = len(data)
        rd = RouteDistinguisher.unpack(data[:8])
        size = data_len - 8
        if not size in [4, 16]:
            raise Notify(3, 5, "Invalid IP size, expect 4 or 16 octets. accuracy size %d" % size)
        ip = IP.unpack(data[8 : 8 + size])

        return cls(rd, ip, afi)

    def json(self, compact=None):
        content = '"arch": %d, ' % self.ARCHTYPE
        content += '"code": %d, ' % self.CODE
        content += '"raw": "%s", ' % self._raw()
        content += '"name": "%s", ' % self.NAME
        content += self.rd.json() + ', '
        content += '"ip": "%s"' % str(self.ip)
        return '{ %s }' % content
