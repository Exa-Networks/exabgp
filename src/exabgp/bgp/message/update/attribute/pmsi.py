"""pmsi.py

Created by Thomas Morin on 2014-06-10.
Copyright (c) 2014-2017 Orange. All rights reserved.
Copyright (c) 2014-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from struct import pack, unpack
from typing import TYPE_CHECKING, ClassVar, Type

from exabgp.util.types import Buffer

if TYPE_CHECKING:
    from exabgp.bgp.message.open.capability.negotiated import Negotiated

from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.update.attribute.attribute import Attribute
from exabgp.protocol.ip import IPv4

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


# Flags(1) + Tunnel Type(1) + MPLS Label(3), before the Tunnel Identifier
PMSI_HEADER_SIZE = 5

# RFC 6514 5 calls the attribute malformed when its tunnel type is undefined. Defined is
# the IANA "P-Multicast Service Interface Tunnel (PMSI Tunnel) Tunnel Types" registry
# (RFC 7385) as it stood on 2026-01-26: 0x00 to 0x08 (RFC 6514, RFC 7524), 0x0A Assisted
# Replication (RFC 9574), 0x0B BIER (RFC 8556), 0x0C and 0x0D SR P2MP (RFC 10018), 0xFF
# wildcard (RFC 8338), and the experimental 0x7B-0x7E and 0xFB-0xFE. 0x80-0xFA is a
# composite tunnel (RFC 8317), defined when the type in its low seven bits is. 0x09,
# 0x0E-0x7A and 0x7F are unassigned or reserved, and are the undefined ones.
ASSIGNED_TUNNEL_TYPES = frozenset({*range(0x00, 0x09), *range(0x0A, 0x0E), 0xFF})
EXPERIMENTAL_TUNNEL_TYPES = frozenset({*range(0x7B, 0x7F), *range(0xFB, 0xFF)})
COMPOSITE_TUNNEL_FIRST = 0x80
COMPOSITE_TUNNEL_LAST = 0xFA
COMPOSITE_TUNNEL_TYPE_MASK = 0x7F

# RFC 6514 5 calls it malformed too when the Tunnel Identifier does not parse as one of its
# type. These types are made of addresses, so their size says it all; RFC 6515 2 says an
# address is four octets for IPv4 and sixteen for IPv6, the AFI notwithstanding.
#   0  no tunnel information: no identifier
#   1  RSVP-TE P2MP: Extended Tunnel ID (an address), Reserved(2), Tunnel ID(2), P2MP ID(4)
#   3, 4, 5  PIM-SSM, PIM-SM, BIDIR-PIM: an address, then a P-multicast group
#   6  Ingress Replication: the endpoint address
# The others are not sized here: 2 and 7 hold an mLDP FEC Element, read by _mldp_fec_error,
# and the identifiers of 8 and above are left as they are.
IDENTIFIER_SIZES: dict[int, tuple[int, ...]] = {
    0: (0,),
    1: (12, 24),
    3: (8, 32),
    4: (8, 32),
    5: (8, 32),
    6: (4, 16),
}
MLDP_TUNNEL_TYPES = (2, 7)
# RFC 6388 2.2 and 3.2: Type(1), Address Family(2), Address Length(1), the root node
# address, Opaque Length(2), the opaque value. Family 1 is IPv4, 2 is IPv6.
MLDP_FEC_HEADER_SIZE = 4
MLDP_OPAQUE_LENGTH_SIZE = 2
MLDP_ROOT_ADDRESSES = ((1, 4), (2, 16))


def _tunnel_type_defined(tunnel_type: int) -> bool:
    if tunnel_type in ASSIGNED_TUNNEL_TYPES or tunnel_type in EXPERIMENTAL_TUNNEL_TYPES:
        return True
    if COMPOSITE_TUNNEL_FIRST <= tunnel_type <= COMPOSITE_TUNNEL_LAST:
        return tunnel_type & COMPOSITE_TUNNEL_TYPE_MASK in ASSIGNED_TUNNEL_TYPES
    return False


def _mldp_fec_error(identifier: Buffer) -> str | None:
    """Why an mLDP tunnel identifier is not one FEC Element, or None when it is."""
    if len(identifier) < MLDP_FEC_HEADER_SIZE:
        return f'an mLDP FEC Element of {len(identifier)} octets'
    family = unpack('!H', identifier[1:3])[0]
    root_size = identifier[3]
    if (family, root_size) not in MLDP_ROOT_ADDRESSES:
        return f'an mLDP root node address of family {family} and {root_size} octets'
    opaque_at = MLDP_FEC_HEADER_SIZE + root_size
    if len(identifier) < opaque_at + MLDP_OPAQUE_LENGTH_SIZE:
        return 'an mLDP FEC Element without its opaque length'
    opaque_size = unpack('!H', identifier[opaque_at : opaque_at + MLDP_OPAQUE_LENGTH_SIZE])[0]
    if len(identifier) != opaque_at + MLDP_OPAQUE_LENGTH_SIZE + opaque_size:
        return 'an mLDP FEC Element whose opaque length is not the rest of the identifier'
    return None


def malformed_pmsi(packed: Buffer) -> str | None:
    """RFC 6514 5: why a PMSI Tunnel attribute value is malformed, or None when it is not."""
    if len(packed) < PMSI_HEADER_SIZE:
        return f'{len(packed)} octets, too short for the fixed header'
    tunnel_type = packed[1]
    if not _tunnel_type_defined(tunnel_type):
        return f'undefined tunnel type {tunnel_type:#04x}'
    identifier = packed[PMSI_HEADER_SIZE:]
    sizes = IDENTIFIER_SIZES.get(tunnel_type, None)
    if sizes is not None and len(identifier) not in sizes:
        return f'a tunnel type {tunnel_type} identifier of {len(identifier)} octets'
    if tunnel_type in MLDP_TUNNEL_TYPES:
        return _mldp_fec_error(identifier)
    return None


# ========================================================================= PMSI
# RFC 6514


class PMSI(Attribute):
    ID: ClassVar = Attribute.CODE.PMSI_TUNNEL
    # RFC 6514 5: an UPDATE carrying a malformed PMSI Tunnel attribute is treated as a
    # withdraw of its routes
    TREAT_AS_WITHDRAW: ClassVar[bool] = True
    FLAG: ClassVar = Attribute.Flag.OPTIONAL | Attribute.Flag.TRANSITIVE
    CACHING: ClassVar[bool] = True
    TUNNEL_TYPE: ClassVar[int] = -1  # Used for subclass registration
    # the size of the tunnel identifier this class reads, None when it reads any.  Another
    # size of the same tunnel type, which malformed_pmsi lets through (an IPv6 endpoint of
    # Ingress Replication), gets the generic PMSI and is shown as hex.
    TUNNEL_SIZE: ClassVar[int | None] = None

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

    def __init__(self, packed: Buffer) -> None:
        """Initialize PMSI from packed wire-format bytes.

        NO validation - trusted internal use only.
        Use from_packet() for wire data or make_pmsi() for semantic construction.

        Args:
            packed: Raw attribute value bytes (flags:1 + tunnel_type:1 + label:3 + tunnel:variable)
        """
        self._packed: Buffer = packed

    @classmethod
    def from_packet(cls, data: Buffer) -> 'PMSI':
        """Validate and create from wire-format bytes.

        Args:
            data: Raw attribute value bytes from wire

        Returns:
            PMSI instance (or appropriate subclass)

        Raises:
            ValueError: If data is too short for the fixed header
            Notify: If the attribute is malformed (RFC 6514 5), which AttributeCollection
                turns into treat-as-withdraw
        """
        if len(data) < PMSI_HEADER_SIZE:
            raise ValueError(f'PMSI requires at least 5 bytes, got {len(data)}')
        reason = malformed_pmsi(data)
        if reason is not None:
            raise Notify(3, 9, f'malformed PMSI Tunnel attribute: {reason}')
        tunnel_type = data[1]
        klass = cls._pmsi_known.get(tunnel_type)
        if klass is None:
            return PMSI(data)
        # a subclass exists to read a tunnel identifier of one shape, and its accessors say
        # so: PMSIIngressReplication.ip hands four bytes to IPv4.ntop(). A size the type
        # allows which is not that shape gets the generic PMSI, which prints it as hex.
        if klass.TUNNEL_SIZE is not None and len(data) - 5 != klass.TUNNEL_SIZE:
            # PMSI, not cls: called on a subclass, cls is that subclass, and returning it
            # is the very thing this check exists to prevent
            return PMSI(data)
        return klass(data)

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

        Raises:
            ValueError: If a receiver would call the attribute malformed (RFC 6514 5)
        """
        if raw_label is not None:
            packed_label = pack('!L', raw_label)[1:4]
        else:
            packed_label = pack('!L', label << 4)[1:4]
        packed = pack('!BB', flags, tunnel_type) + packed_label + tunnel
        reason = malformed_pmsi(packed)
        if reason is not None:
            raise ValueError(f'a PMSI Tunnel attribute with {reason} is malformed (RFC 6514 5)')
        # the same rule as from_packet: a subclass only gets the identifier it can read,
        # otherwise its accessors are handed something they cannot make sense of
        klass = cls._pmsi_known.get(tunnel_type)
        if klass is not None and (klass.TUNNEL_SIZE is None or len(tunnel) == klass.TUNNEL_SIZE):
            return klass(packed)
        return PMSI(packed)

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
        value: int = unpack('!L', b'\0' + self._packed[2:5])[0]
        return value

    @property
    def label(self) -> int:
        """Get MPLS label by unpacking from bytes (raw_label >> 4)."""
        return self.raw_label >> 4

    @property
    def tunnel(self) -> Buffer:
        """Get tunnel identifier bytes."""
        return self._packed[5:]

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, PMSI):
            return False
        return self._packed == other._packed

    def __ne__(self, other: object) -> bool:
        return not self == other

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
    def register_tunnel_type(cls, klass: Type[PMSI]) -> Type[PMSI]:
        """Register a PMSI subclass by tunnel type.

        Note: Named differently from Attribute.register to avoid signature conflict.
        """
        if klass.TUNNEL_TYPE in cls._pmsi_known:
            raise RuntimeError('only one registration for PMSI')
        cls._pmsi_known[klass.TUNNEL_TYPE] = klass
        return klass

    @classmethod
    def unpack_attribute(cls, data: Buffer, negotiated: Negotiated) -> Attribute:
        return cls.from_packet(data)


Attribute.register()(PMSI)


# ================================================================= PMSINoTunnel
# RFC 6514


class PMSINoTunnel(PMSI):
    TUNNEL_TYPE: ClassVar[int] = 0
    TUNNEL_SIZE: ClassVar[int | None] = 0

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


PMSI.register_tunnel_type(PMSINoTunnel)


# ======================================================= PMSIIngressReplication
# RFC 6514


class PMSIIngressReplication(PMSI):
    TUNNEL_TYPE: ClassVar[int] = 6
    TUNNEL_SIZE: ClassVar[int | None] = 4  # an IPv4 address

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
        """The endpoint as an address.

        Every path which builds this class, from_packet for the wire and make_pmsi for our
        own callers, checks the identifier against TUNNEL_SIZE first, so IPv4.ntop() cannot
        be handed anything else. The assertion states that invariant rather than testing
        input: nothing a peer sends can make it false.
        """
        assert len(self.tunnel) == self.TUNNEL_SIZE, 'ingress replication holds an IPv4 address'
        return self.ip


PMSI.register_tunnel_type(PMSIIngressReplication)
