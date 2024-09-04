# encoding: utf-8
"""
segment.py

Created by Thomas Mangin on 2014-06-27.
Copyright (c) 2014-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from exabgp.protocol.ip import IP

from exabgp.util import character
from exabgp.util import ordinal
from exabgp.util import concat_bytes

from exabgp.bgp.message.update.nlri.qualifier import RouteDistinguisher
from exabgp.bgp.message.update.nlri.qualifier import ESI

from exabgp.bgp.message.update.nlri.evpn.nlri import EVPN

from exabgp.bgp.message.notification import Notify

# +---------------------------------------+
# |      RD   (8 octets)                  |
# +---------------------------------------+
# |Ethernet Segment Identifier (10 octets)|
# +---------------------------------------+
# |  IP Address Length (1 octet)          |
# +---------------------------------------+
# |   Originating Router's IP Addr        |
# |          (4 or 16 octets)             |
# +---------------------------------------+

# ===================================================================== EVPNNLRI


@EVPN.register
class EthernetSegment(EVPN):
    CODE = 4
    NAME = "Ethernet Segment"
    SHORT_NAME = "Segment"

    def __init__(self, rd, esi, ip, packed=None, nexthop=None, action=None, addpath=None):
        EVPN.__init__(self, action, addpath)
        self.nexthop = nexthop
        self.rd = rd
        self.esi = esi
        self.ip = ip
        self._pack(packed)

    def __eq__(self, other):
        return (
            isinstance(other, EthernetSegment)
            and self.CODE == other.CODE
            and self.rd == other.rd
            and self.ip == other.ip
        )
        # esi and label must not be part of the comparaison

    def __ne__(self, other):
        return not self.__eq__(other)

    def __str__(self):
        return "%s:%s:%s:%s" % (self._prefix(), self.rd._str(), self.esi, self.ip if self.ip else "")

    def __hash__(self):
        # esi and label MUST *NOT* be part of the hash
        return hash((self.rd, self.ip))

    def _pack(self, packed=None):
        if self._packed:
            return self._packed

        if packed:
            self._packed = packed
            return packed

        self._packed = concat_bytes(
            self.rd.pack(),
            self.esi.pack(),
            character(len(self.ip) * 8 if self.ip else 0),
            self.ip.pack() if self.ip else b'',
        )
        return self._packed

    @classmethod
    def unpack(cls, data):
        rd = RouteDistinguisher.unpack(data[:8])
        esi = ESI.unpack(data[8:18])
        iplen = ordinal(data[18])

        if iplen not in (32, 128):
            raise Notify(
                3,
                5,
                "IP length field is given as %d in current Segment, expecting 32 (IPv4) or 128 (IPv6) bits" % iplen,
            )

        ip = IP.unpack(data[19 : 19 + (iplen // 8)])

        return cls(rd, esi, ip, data)

    def json(self, compact=None):
        content = ' "code": %d, ' % self.CODE
        content += '"parsed": true, '
        content += '"raw": "%s", ' % self._raw()
        content += '"name": "%s", ' % self.NAME
        content += '%s, ' % self.rd.json()
        content += self.esi.json()
        content += ', "ip": "%s"' % str(self.ip)
        return '{%s }' % content
