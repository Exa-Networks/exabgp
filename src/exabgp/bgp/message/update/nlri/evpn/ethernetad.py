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
    """EVPN Route Type 1: Ethernet Auto-Discovery.

    Wire format: type(1) + length(1) + RD(8) + ESI(10) + ETag(4) + Label(3+)
    Uses packed-bytes-first pattern for zero-copy routing.
    """

    CODE: ClassVar[int] = 1
    NAME: ClassVar[str] = 'Ethernet Auto-Discovery'
    SHORT_NAME: ClassVar[str] = 'EthernetAD'

    def __init__(self, packed: bytes) -> None:
        """Create EthernetAD from complete wire-format bytes.

        Args:
            packed: Complete wire format (type + length + payload)
        """
        EVPN.__init__(self, packed)

    @classmethod
    def make_ethernetad(
        cls,
        rd: RouteDistinguisher,
        esi: ESI,
        etag: EthernetTag,
        label: Labels | None,
        action: Action = Action.ANNOUNCE,
        addpath: PathInfo = PathInfo.DISABLED,
    ) -> 'EthernetAD':
        """Factory method to create EthernetAD from semantic parameters.

        Packs fields into wire format immediately (packed-bytes-first pattern).
        Note: nexthop is not part of NLRI - set separately after creation.
        """
        label_to_use = label if label else Labels.NOLABEL
        payload = bytes(rd.pack_rd()) + esi.pack_esi() + etag.pack_etag() + label_to_use.pack_labels()
        # Include type + length header for zero-copy pack
        packed = bytes([cls.CODE, len(payload)]) + payload
        instance = cls(packed)
        instance.action = action
        instance.addpath = addpath
        return instance

    # Wire format offsets (after 2-byte type+length header):
    # RD: bytes 2-10, ESI: bytes 10-20, ETag: bytes 20-24, Labels: bytes 24+

    @property
    def rd(self) -> RouteDistinguisher:
        """Route Distinguisher - unpacked from wire bytes."""
        return RouteDistinguisher.unpack_routedistinguisher(self._packed[2:10])

    @property
    def esi(self) -> ESI:
        """Ethernet Segment Identifier - unpacked from wire bytes."""
        return ESI.unpack_esi(self._packed[10:20])

    @property
    def etag(self) -> EthernetTag:
        """Ethernet Tag - unpacked from wire bytes."""
        return EthernetTag.unpack_etag(self._packed[20:24])

    @property
    def label(self) -> Labels:
        """MPLS Labels - unpacked from wire bytes (variable length)."""
        return Labels.unpack_labels(self._packed[24:])

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
    def unpack_evpn(cls, packed: bytes) -> EVPN:
        """Unpack EthernetAD from complete wire format bytes.

        Args:
            packed: Complete wire format (type + length + payload)

        Returns:
            EthernetAD instance with stored wire bytes
        """
        return cls(packed)

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
