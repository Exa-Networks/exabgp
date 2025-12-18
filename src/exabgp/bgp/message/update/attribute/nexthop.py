"""nexthop.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from exabgp.util.types import Buffer

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

    ID: int = Attribute.CODE.NEXT_HOP
    FLAG: int = Attribute.Flag.TRANSITIVE
    CACHING: ClassVar[bool] = True
    SELF: ClassVar[bool] = False
    TREAT_AS_WITHDRAW: ClassVar[bool] = True
    NO_GENERATION: ClassVar[bool] = True

    # Singleton for "no nexthop" (initialized after class definition)
    UNSET: ClassVar[NextHop]

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
        if not self._packed:
            return AFI.undefined
        return AFI.ipv4 if len(self._packed) == 4 else AFI.ipv6

    def top(self, negotiated: Negotiated | None = None, afi: AFI = AFI.undefined) -> str:
        """Get string representation of the IP address."""
        if not self._packed:
            return ''
        return IP.ntop(self._packed)

    def ton(self, negotiated: Negotiated | None = None, afi: AFI = AFI.undefined) -> Buffer:
        """Get packed bytes representation."""
        return self._packed

    def pack_ip(self) -> Buffer:
        """Get packed bytes (IP interface compatibility)."""
        return self._packed

    def resolve(self, ip: 'IP') -> 'NextHop':
        """Resolve address. For concrete NextHop, returns self (already resolved).

        NextHopSelf subclass overrides to return a new NextHop with the resolved IP.
        """
        return self

    def index(self) -> Buffer:
        """Get the packed data for indexing/caching."""
        return self._packed

    def ipv4(self) -> bool:
        """Check if this is an IPv4 address."""
        return len(self._packed) == 4

    def ipv6(self) -> bool:
        """Check if this is an IPv6 address."""
        return len(self._packed) == 16

    def __bool__(self) -> bool:
        """UNSET is falsy, concrete nexthops are truthy."""
        return bool(self._packed)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, NextHop):
            return False
        return self.ID == other.ID and self.FLAG == other.FLAG and self._packed == other._packed

    def __ne__(self, other: object) -> bool:
        return not self.__eq__(other)

    def __len__(self) -> int:
        return len(self._packed)

    def __repr__(self) -> str:
        if not self._packed:
            return 'NextHop.UNSET'
        return self.top()

    def __hash__(self) -> int:
        return hash(('NextHop', self._packed))

    def __copy__(self) -> 'NextHop':
        """Preserve singleton identity for UNSET."""
        if self is NextHop.UNSET:
            return self
        # Use type(self) to preserve subclass (e.g., NextHopSelf)
        new = object.__new__(type(self))
        new.__dict__.update(self.__dict__)
        return new

    def __deepcopy__(self, memo: dict[int, object]) -> 'NextHop':
        """Preserve singleton identity for UNSET."""
        if self is NextHop.UNSET:
            return self
        # Use type(self) to preserve subclass (e.g., NextHopSelf)
        new = object.__new__(type(self))
        new.__dict__.update(self.__dict__)
        memo[id(self)] = new
        return new

    def pack_attribute(self, negotiated: Negotiated) -> bytes:
        return self._attribute(self._packed)

    @classmethod
    def unpack_attribute(cls, data: Buffer, negotiated: Negotiated) -> Attribute:
        if not data:
            return NextHop.UNSET
        return cls.from_packet(data)


class NextHopSelf(NextHop):
    """Special NextHop that starts unresolved and is resolved in-place via resolve()."""

    SELF: ClassVar[bool] = True

    def __init__(self, afi: AFI) -> None:
        # Don't call super().__init__ - we don't have packed bytes yet
        self._afi: AFI = afi
        self._packed = b''  # Empty = unresolved

    @property
    def afi(self) -> AFI:
        """Get the address family."""
        return self._afi

    @property
    def resolved(self) -> bool:
        """True if resolve() has been called with a concrete IP."""
        return self._packed != b''

    def resolve(self, ip: 'IP') -> 'NextHop':
        """Resolve sentinel to concrete IP. Returns new NextHop (does NOT mutate self)."""
        if self.resolved:
            raise ValueError('NextHopSelf already resolved')
        return NextHop(ip.pack_ip())

    def __repr__(self) -> str:
        if not self.resolved:
            return 'self'
        return IP.ntop(self._packed)

    def ipv4(self) -> bool:
        return self._afi == AFI.ipv4

    def ipv6(self) -> bool:
        return self._afi == AFI.ipv6

    def __bool__(self) -> bool:
        # NextHopSelf is always truthy (even before resolution)
        # Override because _packed may be empty, making len() return 0
        return True

    def pack_attribute(self, negotiated: Negotiated) -> bytes:
        if not self.resolved:
            raise ValueError('NextHopSelf.pack_attribute() called before resolve()')
        return self._attribute(self._packed)

    def __eq__(self, other: object) -> bool:
        raise RuntimeError('do not use __eq__ with NextHopSelf')


# ==================================================================== UNSET Singleton
# Initialize the class-level singleton for "no nexthop"
NextHop.UNSET = NextHop(b'')
