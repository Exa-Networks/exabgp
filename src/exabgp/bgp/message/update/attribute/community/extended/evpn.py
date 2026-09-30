"""evpn.py

The two EVPN extended communities of RFC 7432 section 7 which carry a value exabgp has to
read: the ESI Label (7.5) and the ES-Import Route Target (7.6).

Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from struct import pack
from typing import TYPE_CHECKING, ClassVar

from exabgp.bgp.message.update.attribute.community.extended import ExtendedCommunity
from exabgp.bgp.message.update.attribute.community.extended.rt import RouteTarget
from exabgp.util.types import Buffer

if TYPE_CHECKING:
    from exabgp.bgp.message.open.capability.negotiated import Negotiated

# an extended community is eight octets
EXTENDED_COMMUNITY_SIZE = 8
# RFC 7432 7.5: the low bit of the flags octet is the Single-Active flag
SINGLE_ACTIVE = 0x01
MAC_SIZE = 6


class ESILabel(ExtendedCommunity):
    """RFC 7432 7.5: Type 0x06, Sub-Type 0x01, Flags, two reserved octets, the ESI Label."""

    COMMUNITY_TYPE: ClassVar[int] = 0x06
    COMMUNITY_SUBTYPE: ClassVar[int] = 0x01
    DESCRIPTION: ClassVar[str] = 'esi-label'

    def __init__(self, packed: Buffer) -> None:
        ExtendedCommunity.__init__(self, packed)

    @classmethod
    def make_esi_label(cls, label: int, single_active: bool = False) -> ESILabel:
        assert 0 <= label < (1 << 20), 'an MPLS label is twenty bits'
        flags = SINGLE_ACTIVE if single_active else 0
        packed = pack('!BBBxx', cls.COMMUNITY_TYPE, cls.COMMUNITY_SUBTYPE, flags) + (label << 4).to_bytes(3, 'big')
        return cls(packed)

    @property
    def single_active(self) -> bool:
        return bool(self._packed[2] & SINGLE_ACTIVE)

    @property
    def label(self) -> int:
        # the label is the high twenty bits of the last three octets, as in an NLRI
        return int.from_bytes(bytes(self._packed[5:8]), 'big') >> 4

    def __hash__(self) -> int:
        return hash(bytes(self._packed))

    def __repr__(self) -> str:
        mode = 'single-active' if self.single_active else 'all-active'
        return f'{self.DESCRIPTION}:{self.label}:{mode}'

    @classmethod
    def unpack_attribute(cls, data: Buffer, negotiated: Negotiated | None = None) -> ESILabel:
        return cls(data[:EXTENDED_COMMUNITY_SIZE])


ExtendedCommunity.register_subtype(ESILabel)


class ESImportRouteTarget(RouteTarget):
    """RFC 7432 7.6: Type 0x06, Sub-Type 0x02, and the six octet ES-Import, a MAC address."""

    COMMUNITY_TYPE: ClassVar[int] = 0x06
    COMMUNITY_SUBTYPE: ClassVar[int] = 0x02
    DESCRIPTION: ClassVar[str] = 'es-import'

    def __init__(self, packed: Buffer) -> None:
        RouteTarget.__init__(self, packed)

    @classmethod
    def make_es_import(cls, mac: bytes) -> ESImportRouteTarget:
        assert len(mac) == MAC_SIZE, 'the ES-Import is a six octet MAC address'
        return cls(pack('!BB', cls.COMMUNITY_TYPE, cls.COMMUNITY_SUBTYPE) + mac)

    @property
    def mac(self) -> str:
        return ':'.join(f'{octet:02x}' for octet in bytes(self._packed[2:8]))

    def __hash__(self) -> int:
        return hash(bytes(self._packed))

    def __repr__(self) -> str:
        return f'{self.DESCRIPTION}:{self.mac}'

    @classmethod
    def unpack_attribute(cls, data: Buffer, negotiated: Negotiated | None = None) -> ESImportRouteTarget:
        return cls(data[:EXTENDED_COMMUNITY_SIZE])


ExtendedCommunity.register_subtype(ESImportRouteTarget)
