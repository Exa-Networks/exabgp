"""ethernetad.py

Created by Thomas Mangin on 2014-06-27.
Copyright (c) 2014-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from typing import ClassVar

from exabgp.bgp.message import Action
from exabgp.bgp.message.update.nlri.evpn.nlri import EVPN
from exabgp.bgp.message.update.nlri.qualifier import ESI, EthernetTag, Labels, RouteDistinguisher
from exabgp.bgp.message.update.nlri.qualifier.path import PathInfo
from exabgp.protocol.ip import IP
from exabgp.util.types import Buffer

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


@EVPN.register_evpn_route
class EthernetAD(EVPN):
    CODE: ClassVar[int] = 1
    NAME: ClassVar[str] = 'Ethernet Auto-Discovery'
    SHORT_NAME: ClassVar[str] = 'EthernetAD'

    def __init__(
        self,
        packed: Buffer,
        action: Action,
        addpath: PathInfo | None = None,
        nexthop: IP = IP.NoNextHop,
    ) -> None:
        EVPN.__init__(self, action, addpath)
        self._packed = packed
        self.nexthop = nexthop

    @classmethod
    def make_ethernetad(
        cls,
        rd: RouteDistinguisher,
        esi: ESI,
        etag: EthernetTag,
        label: Labels | None,
        nexthop: IP = IP.NoNextHop,
        action: Action | None = None,
        addpath: PathInfo | None = None,
    ) -> 'EthernetAD':
        """Factory method to create EthernetAD from semantic parameters."""
        label_to_use = label if label else Labels.NOLABEL
        packed = bytes(rd.pack_rd()) + esi.pack_esi() + etag.pack_etag() + label_to_use.pack_labels()
        return cls(packed, nexthop, action, addpath)

    @property
    def rd(self) -> RouteDistinguisher:
        return RouteDistinguisher.unpack_routedistinguisher(self._packed[:8])

    @property
    def esi(self) -> ESI:
        return ESI.unpack_esi(self._packed[8:18])

    @property
    def etag(self) -> EthernetTag:
        return EthernetTag.unpack_etag(self._packed[18:22])

    @property
    def label(self) -> Labels:
        # Labels are variable length (3 bytes per label), consume all remaining bytes
        return Labels.unpack_labels(self._packed[22:])

    def __eq__(self, other: object) -> bool:
        return (
            isinstance(other, EthernetAD)
            and self.CODE == other.CODE
            and self.rd == other.rd
            and self.etag == other.etag
        )
        # esi and label must not be part of the comparaison

    def __ne__(self, other: object) -> bool:
        return not self.__eq__(other)

    def __str__(self) -> str:
        return '{}:{}:{}:{}:{}'.format(self._prefix(), self.rd._str(), self.esi, self.etag, self.label)

    def __hash__(self) -> int:
        # esi and label MUST *NOT* be part of the hash
        return hash((self.rd, self.etag))

    @classmethod
    def unpack_evpn(cls, data: Buffer) -> EVPN:
        return cls(data)

    def json(self, compact: bool | None = None) -> str:
        content = ' "code": %d, ' % self.CODE
        content += '"parsed": true, '
        content += '"raw": "{}", '.format(self._raw())
        content += '"name": "{}", '.format(self.NAME)
        content += '{}, '.format(self.rd.json())
        content += '{}, '.format(self.esi.json())
        content += '{}, '.format(self.etag.json())
        content += '{} '.format(self.label.json())
        return '{{{}}}'.format(content)
