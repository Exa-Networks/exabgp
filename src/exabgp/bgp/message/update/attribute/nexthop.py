"""nexthop.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from exabgp.util.types import Buffer
from typing import TYPE_CHECKING, ClassVar

if TYPE_CHECKING:
    from exabgp.bgp.message.open.capability.negotiated import Negotiated

from exabgp.bgp.message.update.attribute.attribute import Attribute
from exabgp.protocol.family import AFI
from exabgp.protocol.ip import IP

# ================================================================== NextHop (3)


@Attribute.register()
class NextHop(Attribute):
    """Next Hop attribute (code 3).

    Stores packed wire-format bytes (4 bytes for IPv4, 16 bytes for IPv6).
    Delegates IP functionality via composition rather than inheritance.
    """

    ID: ClassVar[int] = Attribute.CODE.NEXT_HOP
    FLAG: ClassVar[int] = Attribute.Flag.TRANSITIVE
    CACHING: ClassVar[bool] = True
    SELF: ClassVar[bool] = False
    TREAT_AS_WITHDRAW: ClassVar[bool] = True
    NO_GENERATION: ClassVar[bool] = True

    def __init__(self, packed: Buffer) -> None:
        """Initialize from packed wire-format bytes.

        NO validation - trusted internal use only.
        Use from_packet() for wire data or make_nexthop() for semantic construction.

        Args:
            packed: Raw IP address bytes (4 for IPv4, 16 for IPv6)
        """
        self._packed: Buffer = packed

    @classmethod
    def from_packet(cls, data: Buffer) -> 'NextHop':
        """Validate and create from wire-format bytes.

        Args:
            data: Raw attribute value bytes from wire

        Returns:
            NextHop instance

        Raises:
            ValueError: If data length is invalid
        """
        if len(data) not in (4, 16):
            raise ValueError(f'NextHop must be 4 or 16 bytes, got {len(data)}')
        return cls(data)

    @classmethod
    def from_string(cls, ip_string: str) -> 'NextHop':
        """Create from IP address string.

        Args:
            ip_string: IP address as string (e.g., '192.168.1.1' or '2001:db8::1')

        Returns:
            NextHop instance
        """
        packed = IP.pton(ip_string)
        return cls(packed)

    @property
    def afi(self) -> AFI:
        """Get the address family."""
        return AFI.ipv4 if len(self._packed) == 4 else AFI.ipv6

    def top(self, negotiated: Negotiated | None = None, afi: AFI = AFI.undefined) -> str:
        """Get string representation of the IP address."""
        return IP.ntop(self._packed)

    def ton(self, negotiated: Negotiated | None = None, afi: AFI = AFI.undefined) -> bytes:
        """Get packed bytes representation."""
        return self._packed

    def pack_ip(self) -> bytes:
        """Get packed bytes (IP interface compatibility)."""
        return self._packed

    def index(self) -> bytes:
        """Get the packed data for indexing/caching."""
        return self._packed

    def ipv4(self) -> bool:
        """Check if this is an IPv4 address."""
        return len(self._packed) == 4

    def ipv6(self) -> bool:
        """Check if this is an IPv6 address."""
        return len(self._packed) == 16

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, NextHop):
            return False
        return self.ID == other.ID and self.FLAG == other.FLAG and self._packed == other._packed

    def __ne__(self, other: object) -> bool:
        return not self.__eq__(other)

    def __len__(self) -> int:
        return len(self._packed)

    def __repr__(self) -> str:
        return self.top()

    def __hash__(self) -> int:
        return hash(('NextHop', self._packed))

    def pack_attribute(self, negotiated: Negotiated) -> bytes:
        return self._attribute(self._packed)

    @classmethod
    def unpack_attribute(cls, data: Buffer, negotiated: Negotiated) -> 'NextHop | IP':
        if not data:
            return IP.NoNextHop
        return cls.from_packet(data)


class NextHopSelf(NextHop):
    """Special NextHop that resolves to the local address at pack time."""

    SELF: ClassVar[bool] = True

    def __init__(self, afi: AFI) -> None:
        # Don't call super().__init__ - we don't have packed bytes yet
        self._afi: AFI = afi
        self._packed = b''  # Placeholder, resolved at pack time

    @property
    def afi(self) -> AFI:
        """Get the address family."""
        return self._afi

    def __repr__(self) -> str:
        return 'self'

    def ipv4(self) -> bool:
        return self._afi == AFI.ipv4

    def ipv6(self) -> bool:
        return self._afi == AFI.ipv6

    def __bool__(self) -> bool:
        # NextHopSelf is always truthy (resolved at pack time)
        # Override because _packed is empty, making len() return 0
        return True

    def pack_attribute(self, negotiated: Negotiated) -> bytes:
        return self._attribute(negotiated.nexthopself(self._afi).ton())

    def ton(self, negotiated: Negotiated, afi: AFI = AFI.undefined) -> bytes:
        return negotiated.nexthopself(afi).ton()

    def __eq__(self, other: object) -> bool:
        raise RuntimeError('do not use __eq__ with NextHopSelf')
