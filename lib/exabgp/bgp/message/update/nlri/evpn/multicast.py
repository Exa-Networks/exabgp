"""
multicast.py

Created by Thomas Morin on 2014-06-23.
Copyright (c) 2014-2017 Orange. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from exabgp.protocol.ip import IP
from exabgp.util import character
from exabgp.util import ordinal
from exabgp.util import concat_bytes
from exabgp.bgp.message.update.nlri.qualifier import RouteDistinguisher
from exabgp.bgp.message.update.nlri.qualifier import EthernetTag

from exabgp.bgp.message.update.nlri.evpn.nlri import EVPN

# +---------------------------------------+
# |      RD   (8 octets)                  |
# +---------------------------------------+
# |  Ethernet Tag ID (4 octets)           |
# +---------------------------------------+
# |  IP Address Length (1 octet)          |
# +---------------------------------------+
# |   Originating Router's IP Addr        |
# |          (4 or 16 octets)             |
# +---------------------------------------+

# ===================================================================== EVPNNLRI


@EVPN.register
class Multicast(EVPN):
    CODE = 3
    NAME = "Inclusive Multicast Ethernet Tag"
    SHORT_NAME = "Multicast"

    def __init__(self, rd, etag, ip, packed=None, nexthop=None, action=None, addpath=None):
        EVPN.__init__(self, action, addpath)
        self.nexthop = nexthop
        self.rd = rd
        self.etag = etag
        self.ip = ip
        self._pack(packed)

    def __ne__(self, other):
        return not self.__eq__(other)

    def __str__(self):
        return "%s:%s:%s:%s" % (self._prefix(), self.rd._str(), self.etag, self.ip,)

    def __hash__(self):
        return hash((self.afi, self.safi, self.CODE, self.rd, self.etag, self.ip))

    def _pack(self, packed=None):
        if self._packed:
            return self._packed

        if packed:
            self._packed = packed
            return packed

        self._packed = concat_bytes(self.rd.pack(), self.etag.pack(), character(len(self.ip) * 8), self.ip.pack())
        return self._packed

    @classmethod
    def unpack(cls, data):
        rd = RouteDistinguisher.unpack(data[:8])
        etag = EthernetTag.unpack(data[8:12])
        iplen = ordinal(data[12])
        if iplen not in (4 * 8, 16 * 8):
            raise Exception("IP len is %d, but EVPN route currently support only IPv4" % iplen)
        ip = IP.unpack(data[13 : 13 + iplen // 8])
        return cls(rd, etag, ip, data)

    def json(self, compact=None):
        content = ' "code": %d, ' % self.CODE
        content += '"parsed": true, '
        content += '"raw": "%s", ' % self._raw()
        content += '"name": "%s", ' % self.NAME
        content += '%s, ' % self.rd.json()
        content += self.etag.json()
        if self.ip:
            content += ', "ip": "%s"' % str(self.ip)
        return '{%s }' % content
