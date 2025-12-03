"""pmsi.py

Created by Thomas Morin on 2014-06-10.
Copyright (c) 2014-2017 Orange. All rights reserved.
Copyright (c) 2014-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from struct import pack
from struct import unpack
from typing import TYPE_CHECKING, ClassVar, Type

if TYPE_CHECKING:
    from exabgp.bgp.message.open.capability.negotiated import Negotiated

from exabgp.protocol.ip import IPv4
from exabgp.bgp.message.update.attribute.attribute import Attribute

# https://tools.ietf.org/html/rfc6514#section-5
#
#  +---------------------------------+
#  |  Flags (1 octet)                |
#  +---------------------------------+
#  |  Tunnel Type (1 octets)         |
#  +---------------------------------+
#  |  MPLS Label (3 octets)          |
#  +---------------------------------+
#  |  Tunnel Identifier (variable)   |
#  +---------------------------------+


# ========================================================================= PMSI
# RFC 6514


@Attribute.register()
class PMSI(Attribute):
    ID = Attribute.CODE.PMSI_TUNNEL
    FLAG = Attribute.Flag.OPTIONAL | Attribute.Flag.TRANSITIVE
    CACHING = True
    TUNNEL_TYPE: ClassVar[int] = -1  # Used for subclass registration

    _pmsi_known: ClassVar[dict[int, Type[PMSI]]] = dict()
    _name: ClassVar[dict[int, str]] = {
        0: 'No tunnel',
        1: 'RSVP-TE P2MP LSP',
        2: 'mLDP P2MP LSP',
        3: 'PIM-SSM Tree',
        4: 'PIM-SM Tree',
        5: 'BIDIR-PIM Tree',
        6: 'Ingress Replication',
        7: 'mLDP MP2MP LSP',
    }

    def __init__(self, packed: bytes) -> None:
        """Initialize PMSI from packed wire-format bytes.

        NO validation - trusted internal use only.
        Use from_packet() for wire data or make_pmsi() for semantic construction.

        Args:
            packed: Raw attribute value bytes (flags:1 + tunnel_type:1 + label:3 + tunnel:variable)
        """
        self._packed: bytes = packed

    @classmethod
    def from_packet(cls, data: bytes) -> 'PMSI':
        """Validate and create from wire-format bytes.

        Args:
            data: Raw attribute value bytes from wire

        Returns:
            PMSI instance (or appropriate subclass)

        Raises:
            ValueError: If data is malformed
        """
        if len(data) < 5:
            raise ValueError(f'PMSI requires at least 5 bytes, got {len(data)}')
        tunnel_type = data[1]
        if tunnel_type in cls._pmsi_known:
            return cls._pmsi_known[tunnel_type](data)
        return cls(data)

    @classmethod
    def make_pmsi(cls, tunnel_type: int, flags: int, label: int, tunnel: bytes, raw_label: int | None = None) -> 'PMSI':
        """Create PMSI from semantic values.

        Args:
            tunnel_type: Tunnel type (0-7 for known types)
            flags: PMSI flags
            label: MPLS label (will be shifted left by 4)
            tunnel: Tunnel identifier bytes
            raw_label: Raw 24-bit label value (if provided, used instead of label << 4)

        Returns:
            PMSI instance
        """
        if raw_label is not None:
            packed_label = pack('!L', raw_label)[1:4]
        else:
            packed_label = pack('!L', label << 4)[1:4]
        packed = pack('!BB', flags, tunnel_type) + packed_label + tunnel
        if tunnel_type in cls._pmsi_known:
            return cls._pmsi_known[tunnel_type](packed)
        return cls(packed)

    @property
    def flags(self) -> int:
        """Get PMSI flags by unpacking from bytes."""
        return self._packed[0]

    @property
    def tunnel_type(self) -> int:
        """Get tunnel type by unpacking from bytes."""
        return self._packed[1]

    @property
    def raw_label(self) -> int:
        """Get raw 24-bit label value by unpacking from bytes."""
        return unpack('!L', b'\0' + self._packed[2:5])[0]

    @property
    def label(self) -> int:
        """Get MPLS label by unpacking from bytes (raw_label >> 4)."""
        return self.raw_label >> 4

    @property
    def tunnel(self) -> bytes:
        """Get tunnel identifier bytes."""
        return self._packed[5:]

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, PMSI):
            return False
        return self._packed == other._packed

    def __ne__(self, other: object) -> bool:
        return not self.__eq__(other)

    @staticmethod
    def name(tunnel_type: int) -> str:
        return PMSI._name.get(tunnel_type, 'unknown')

    def pack_attribute(self, negotiated: Negotiated) -> bytes:
        return self._attribute(self._packed)

    def __len__(self) -> int:
        return len(self._packed)

    def prettytunnel(self) -> str:
        return '0x' + ''.join('{:02X}'.format(_) for _ in self.tunnel) if self.tunnel else ''

    def __repr__(self) -> str:
        raw = self.raw_label
        lbl = self.label
        # Check if there's extra info in raw_label (bottom of stack bit, etc.)
        if raw != (lbl << 4):
            label_repr = f'{lbl}({raw})'
        else:
            label_repr = str(lbl) if lbl else '0'
        return 'pmsi:{}:{}:{}:{}'.format(
            self.name(self.tunnel_type).replace(' ', '').lower(),
            str(self.flags),
            label_repr,
            self.prettytunnel(),
        )

    @classmethod
    def register(cls, klass: Type[PMSI]) -> Type[PMSI]:  # type: ignore[override]
        if klass.TUNNEL_TYPE in cls._pmsi_known:
            raise RuntimeError('only one registration for PMSI')
        cls._pmsi_known[klass.TUNNEL_TYPE] = klass
        return klass

    @classmethod
    def unpack_attribute(cls, data: bytes, negotiated: Negotiated) -> PMSI:
        return cls.from_packet(data)


# ================================================================= PMSINoTunnel
# RFC 6514


@PMSI.register
class PMSINoTunnel(PMSI):
    TUNNEL_TYPE: ClassVar[int] = 0

    @classmethod
    def make_no_tunnel(cls, flags: int = 0, label: int = 0, raw_label: int | None = None) -> 'PMSINoTunnel':
        """Create PMSINoTunnel from semantic values.

        Args:
            flags: PMSI flags
            label: MPLS label
            raw_label: Raw 24-bit label value (optional)

        Returns:
            PMSINoTunnel instance
        """
        if raw_label is not None:
            packed_label = pack('!L', raw_label)[1:4]
        else:
            packed_label = pack('!L', label << 4)[1:4]
        return cls(pack('!BB', flags, cls.TUNNEL_TYPE) + packed_label)

    def prettytunnel(self) -> str:
        return ''


# ======================================================= PMSIIngressReplication
# RFC 6514


@PMSI.register
class PMSIIngressReplication(PMSI):
    TUNNEL_TYPE: ClassVar[int] = 6

    @classmethod
    def make_ingress_replication(
        cls, ip: str, flags: int = 0, label: int = 0, raw_label: int | None = None
    ) -> 'PMSIIngressReplication':
        """Create PMSIIngressReplication from semantic values.

        Args:
            ip: IPv4 address string for tunnel endpoint
            flags: PMSI flags
            label: MPLS label
            raw_label: Raw 24-bit label value (optional)

        Returns:
            PMSIIngressReplication instance
        """
        if raw_label is not None:
            packed_label = pack('!L', raw_label)[1:4]
        else:
            packed_label = pack('!L', label << 4)[1:4]
        return cls(pack('!BB', flags, cls.TUNNEL_TYPE) + packed_label + IPv4.pton(ip))

    @property
    def ip(self) -> str:
        """Get tunnel endpoint IP address."""
        return IPv4.ntop(self.tunnel)

    def prettytunnel(self) -> str:
        return self.ip
