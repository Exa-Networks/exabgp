"""
ethernetad.py

Created by Thomas Mangin on 2014-06-27.
Copyright (c) 2014-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

# from struct import pack
# from struct import unpack

from exabgp.util import concat_bytes

# from exabgp.protocol.family import AFI
# from exabgp.protocol.family import SAFI
# from exabgp.bgp.message.update.nlri.qualifier import ESI

from exabgp.bgp.message.update.nlri.qualifier import RouteDistinguisher
from exabgp.bgp.message.update.nlri.qualifier import Labels
from exabgp.bgp.message.update.nlri.qualifier import ESI
from exabgp.bgp.message.update.nlri.qualifier import EthernetTag

from exabgp.bgp.message.update.nlri.evpn.nlri import EVPN

# +---------------------------------------+
# |      RD   (8 octets)                  |
# +---------------------------------------+
# |Ethernet Segment Identifier (10 octets)|
# +---------------------------------------+
# |  Ethernet Tag ID (4 octets)           |
# +---------------------------------------+
# |  MPLS Label (3 octets)                |
# +---------------------------------------+

# ===================================================================== EVPNNLRI


@EVPN.register
class EthernetAD(EVPN):
    CODE = 1
    NAME = "Ethernet Auto-Discovery"
    SHORT_NAME = "EthernetAD"

    def __init__(self, rd, esi, etag, label, packed=None, nexthop=None, action=None, addpath=None):
        EVPN.__init__(self, action, addpath)
        self.nexthop = nexthop
        self.rd = rd
        self.esi = esi
        self.etag = etag
        self.label = label if label else Labels.NOLABEL
        self._pack(packed)

    def __eq__(self, other):
        return (
            isinstance(other, EthernetAD)
            and self.CODE == other.CODE
            and self.rd == other.rd
            and self.etag == other.etag
        )
        # esi and label must not be part of the comparaison

    def __ne__(self, other):
        return not self.__eq__(other)

    def __str__(self):
        return "%s:%s:%s:%s:%s" % (self._prefix(), self.rd._str(), self.esi, self.etag, self.label)

    def __hash__(self):
        # esi and label MUST *NOT* be part of the hash
        return hash((self.rd, self.etag))

    def _pack(self, packed=None):
        if self._packed:
            return self._packed

        if packed:
            self._packed = packed
            return packed

        self._packed = concat_bytes(self.rd.pack(), self.esi.pack(), self.etag.pack(), self.label.pack())
        return self._packed

    @classmethod
    def unpack(cls, data):
        rd = RouteDistinguisher.unpack(data[:8])
        esi = ESI.unpack(data[8:18])
        etag = EthernetTag.unpack(data[18:22])
        label = Labels.unpack(data[22:25])

        return cls(rd, esi, etag, label, data)

    def json(self, compact=None):
        content = ' "code": %d, ' % self.CODE
        content += '"parsed": true, '
        content += '"raw": "%s", ' % self._raw()
        content += '"name": "%s", ' % self.NAME
        content += '%s, ' % self.rd.json()
        content += '%s, ' % self.esi.json()
        content += '%s, ' % self.etag.json()
        content += '%s ' % self.label.json()
        return '{%s}' % content
