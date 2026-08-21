"""ethernetad.py

Created by Thomas Mangin on 2014-06-27.
Copyright (c) 2014-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from typing import ClassVar

from exabgp.bgp.message import Action
from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.update.nlri.evpn.nlri import EVPN
from exabgp.bgp.message.update.nlri.qualifier import ESI, EthernetTag, Labels, RouteDistinguisher
from exabgp.bgp.message.update.nlri.qualifier.path import PathInfo
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


@EVPN.register_evpn_route(code=1)
class EthernetAD(EVPN):
    """EVPN Route Type 1: Ethernet Auto-Discovery.

    Wire format: type(1) + length(1) + RD(8) + ESI(10) + ETag(4) + Label(3+)
    Uses packed-bytes-first pattern for zero-copy routing.
    """

    NAME: ClassVar[str] = 'Ethernet Auto-Discovery'
    SHORT_NAME: ClassVar[str] = 'EthernetAD'

    def __init__(self, packed: Buffer) -> None:
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
        action: Action = Action.UNSET,
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
    def unpack_evpn(cls, packed: Buffer) -> EVPN:
        """Unpack EthernetAD from complete wire format bytes.

        Args:
            packed: Complete wire format (type + length + payload)

        Returns:
            EthernetAD instance with stored wire bytes
        """
        # header(2) + RD(8) + ESI(10) + ETag(4), the label stack follows
        cls.check_length(packed, 24)
        if (len(packed) - 24) % 3:
            raise Notify(3, 10, 'Ethernet A-D EVPN NLRI has a truncated label stack')
        return cls(packed)

    def json(self, announced: bool = True, compact: bool | None = None) -> str:
        """Serialise to JSON.

        The members are collected and joined rather than concatenated with their own
        separators: a member which renders empty, an EVPN route with no label stack being
        the one Hypothesis found, otherwise leaves a stray comma behind and the line is
        not JSON any more.
        """
        members = [
            '"code": %d' % self.CODE,
            '"parsed": true',
            '"raw": "{}"'.format(self._raw()),
            '"name": "{}"'.format(self.NAME),
        ]
        members.append(self.rd.json())
        members.append(self.esi.json())
        members.append(self.etag.json())
        members.append(self.label.json())
        return '{{ {} }}'.format(', '.join(member for member in members if member))
