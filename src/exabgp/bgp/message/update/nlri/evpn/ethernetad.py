"""ethernetad.py

Created by Thomas Mangin on 2014-06-27.
Copyright (c) 2014-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from typing import ClassVar, Optional, Union

from exabgp.bgp.message.update.nlri.qualifier.path import PathInfo
from exabgp.protocol.ip import IP, _NoNextHop

from exabgp.bgp.message.update.nlri.qualifier import RouteDistinguisher
from exabgp.bgp.message.update.nlri.qualifier import Labels
from exabgp.bgp.message.update.nlri.qualifier import ESI
from exabgp.bgp.message.update.nlri.qualifier import EthernetTag

from exabgp.bgp.message.update.nlri.evpn.nlri import EVPN
from exabgp.bgp.message import Action

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
    CODE: ClassVar[int] = 1
    NAME: ClassVar[str] = 'Ethernet Auto-Discovery'
    SHORT_NAME: ClassVar[str] = 'EthernetAD'

    def __init__(
        self,
        rd: RouteDistinguisher,
        esi: ESI,
        etag: EthernetTag,
        label: Optional[Labels],
        packed: Optional[bytes] = None,
        nexthop: Optional[Union[IP, _NoNextHop]] = None,
        action: Optional[Action] = None,
        addpath: Optional[PathInfo] = None,
    ) -> None:
        EVPN.__init__(self, action, addpath)  # type: ignore[arg-type]
        self.nexthop = nexthop
        self.rd = rd
        self.esi = esi
        self.etag = etag
        self.label = label if label else Labels.NOLABEL
        self._pack(packed)

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

    def _pack(self, packed: Optional[bytes] = None) -> bytes:
        if self._packed:
            return self._packed

        if packed:
            self._packed = packed
            return packed

        self._packed = self.rd.pack_rd() + self.esi.pack_esi() + self.etag.pack_etag() + self.label.pack_labels()  # type: ignore[union-attr]
        return self._packed

    @classmethod
    def unpack_evpn_route(cls, data: bytes) -> EthernetAD:
        rd = RouteDistinguisher.unpack_routedistinguisher(data[:8])
        esi = ESI.unpack_esi(data[8:18])
        etag = EthernetTag.unpack_etag(data[18:22])
        label = Labels.unpack_labels(data[22:25])

        return cls(rd, esi, etag, label, data)

    def json(self, compact: Optional[bool] = None) -> str:
        content = ' "code": %d, ' % self.CODE
        content += '"parsed": true, '
        content += '"raw": "{}", '.format(self._raw())
        content += '"name": "{}", '.format(self.NAME)
        content += '{}, '.format(self.rd.json())
        content += '{}, '.format(self.esi.json())
        content += '{}, '.format(self.etag.json())
        content += '{} '.format(self.label.json())  # type: ignore[union-attr]
        return '{{{}}}'.format(content)
