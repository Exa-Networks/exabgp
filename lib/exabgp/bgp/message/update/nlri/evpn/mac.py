"""
mac.py

Created by Thomas Morin on 2014-06-23.
Copyright (c) 2014-2017 Orange. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from exabgp.protocol.ip import IP
from exabgp.util import character
from exabgp.util import ordinal
from exabgp.util import concat_bytes
from exabgp.bgp.message.update.nlri.qualifier import RouteDistinguisher
from exabgp.bgp.message.update.nlri.qualifier import Labels
from exabgp.bgp.message.update.nlri.qualifier import ESI
from exabgp.bgp.message.update.nlri.qualifier import EthernetTag
from exabgp.bgp.message.update.nlri.qualifier import MAC as MACQUAL

from exabgp.bgp.message.update.nlri import NLRI

from exabgp.bgp.message.update.nlri.evpn.nlri import EVPN

from exabgp.bgp.message.notification import Notify

# +---------------------------------------+
# |      RD   (8 octets)                  |
# +---------------------------------------+
# |Ethernet Segment Identifier (10 octets)|
# +---------------------------------------+
# |  Ethernet Tag ID (4 octets)           |
# +---------------------------------------+
# |  MAC Address Length (1 octet)         |
# +---------------------------------------+
# |  MAC Address (6 octets)               |  48 bits is 6 bytes
# +---------------------------------------+
# |  IP Address Length (1 octet)          |  zero if IP Address field absent
# +---------------------------------------+
# |  IP Address (4 or 16 octets)          |
# +---------------------------------------+
# |  MPLS Label (3 octets)                |
# +---------------------------------------+

# ===================================================================== EVPNNLRI


@EVPN.register
class MAC(EVPN):
    CODE = 2
    NAME = "MAC/IP advertisement"
    SHORT_NAME = "MACAdv"

    def __init__(self, rd, esi, etag, mac, maclen, label, ip, packed=None, nexthop=None, action=None, addpath=None):
        EVPN.__init__(self, action, addpath)
        self.nexthop = nexthop
        self.rd = rd
        self.esi = esi
        self.etag = etag
        self.maclen = maclen
        self.mac = mac
        self.ip = ip
        self.label = label if label else Labels.NOLABEL
        self._pack(packed)

    # XXX: we have to ignore a part of the route
    def index(self):
        return EVPN.index(self)

    def __eq__(self, other):
        return (
            isinstance(other, MAC)
            and self.CODE == other.CODE
            and self.rd == other.rd
            and self.etag == other.etag
            and self.mac == other.mac
            and self.ip == other.ip
        )
        # esi and label must not be part of the comparaison

    def __ne__(self, other):
        return not self.__eq__(other)

    def __str__(self):
        return "%s:%s:%s:%s:%s%s:%s:%s" % (
            self._prefix(),
            self.rd._str(),
            self.esi,
            self.etag,
            self.mac,
            "" if len(self.mac) == 48 else "/%d" % self.maclen,
            self.ip if self.ip else "",
            self.label,
        )

    def __hash__(self):
        # esi and label MUST *NOT* be part of the hash
        return hash((self.rd, self.etag, self.mac, self.ip))

    def _pack(self, packed=None):
        if self._packed:
            return self._packed

        if packed:
            self._packed = packed
            return packed

        self._packed = concat_bytes(
            self.rd.pack(),
            self.esi.pack(),
            self.etag.pack(),
            character(self.maclen),  # only 48 supported by the draft
            self.mac.pack(),
            character(len(self.ip) * 8 if self.ip else 0),
            self.ip.pack() if self.ip else b'',
            self.label.pack(),
        )
        return self._packed

    @classmethod
    def unpack(cls, data):
        datalen = len(data)
        rd = RouteDistinguisher.unpack(data[:8])
        esi = ESI.unpack(data[8:18])
        etag = EthernetTag.unpack(data[18:22])
        maclength = ordinal(data[22])

        if maclength > 48 or maclength < 0:
            raise Notify(3, 5, 'invalid MAC Address length in %s' % cls.NAME)
        end = 23 + 6  # MAC length MUST be 6

        mac = MACQUAL.unpack(data[23:end])

        length = ordinal(data[end])
        iplen = length / 8

        if datalen in [33, 36]:  # No IP information (1 or 2 labels)
            iplenUnpack = 0
            if iplen != 0:
                raise Notify(3, 5, "IP length is given as %d, but current MAC route has no IP information" % iplen)
        elif datalen in [37, 40]:  # Using IPv4 addresses (1 or 2 labels)
            iplenUnpack = 4
            if iplen > 32 or iplen < 0:
                raise Notify(
                    3,
                    5,
                    "IP field length is given as %d, but current MAC route is IPv4 and valus is out of range" % iplen,
                )
        elif datalen in [49, 52]:  # Using IPv6 addresses (1 or 2 labels)
            iplenUnpack = 16
            if iplen > 128 or iplen < 0:
                raise Notify(
                    3,
                    5,
                    "IP field length is given as %d, but current MAC route is IPv6 and valus is out of range" % iplen,
                )
        else:
            raise Notify(
                3, 5, "Data field length is given as %d, but does not match one of the expected lengths" % datalen
            )

        payload = data[end + 1 : end + 1 + iplenUnpack]
        if payload:
            ip = IP.unpack(data[end + 1 : end + 1 + iplenUnpack])
        else:
            ip = None
        label = Labels.unpack(data[end + 1 + iplenUnpack : end + 1 + iplenUnpack + 3])

        return cls(rd, esi, etag, mac, maclength, label, ip, data)

    def json(self, compact=None):
        content = ' "code": %d, ' % self.CODE
        content += '"parsed": true, '
        content += '"raw": "%s", ' % self._raw()
        content += '"name": "%s", ' % self.NAME
        content += '%s, ' % self.rd.json()
        content += '%s, ' % self.esi.json()
        content += '%s, ' % self.etag.json()
        content += '%s, ' % self.mac.json()
        content += self.label.json()
        if self.ip:
            content += ', "ip": "%s"' % str(self.ip)
        return '{%s }' % content
