"""community.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from struct import pack
from struct import unpack
from typing import TYPE_CHECKING, ClassVar

if TYPE_CHECKING:
    from exabgp.bgp.message.open.capability.negotiated import Negotiated
from exabgp.util.types import Buffer


# ==================================================================== Community
#


class Community:
    """Standard BGP Community (RFC 1997).

    Stores packed wire-format bytes (4 bytes).
    """

    MAX: ClassVar[int] = 0xFFFFFFFF

    NO_EXPORT: ClassVar[bytes] = pack('!L', 0xFFFFFF01)
    NO_ADVERTISE: ClassVar[bytes] = pack('!L', 0xFFFFFF02)
    NO_EXPORT_SUBCONFED: ClassVar[bytes] = pack('!L', 0xFFFFFF03)
    NO_PEER: ClassVar[bytes] = pack('!L', 0xFFFFFF04)
    BLACKHOLE: ClassVar[bytes] = pack('!L', 0xFFFF029A)

    cache: ClassVar[dict[bytes, Community]] = {}
    caching: ClassVar[bool] = True

    def __init__(self, packed: Buffer) -> None:
        """Initialize from packed wire-format bytes.

        NO validation - trusted internal use only.
        Use from_packet() for wire data or make_community() for semantic construction.

        Args:
            packed: Raw community bytes (4 bytes)
        """
        self._packed: Buffer = packed

    @classmethod
    def from_packet(cls, data: Buffer) -> 'Community':
        """Validate and create from wire-format bytes.

        Args:
            data: Raw community bytes from wire

        Returns:
            Community instance

        Raises:
            ValueError: If data length is not 4
        """
        if len(data) != 4:
            raise ValueError(f'Community must be 4 bytes, got {len(data)}')
        return cls(data)

    @classmethod
    def make_community(cls, asn: int, value: int) -> 'Community':
        """Create from ASN and value.

        Args:
            asn: 16-bit ASN portion
            value: 16-bit value portion

        Returns:
            Community instance
        """
        packed = pack('!HH', asn, value)
        return cls(packed)

    @classmethod
    def make_wellknown(cls, value: int) -> 'Community':
        """Create from well-known community value.

        Args:
            value: 32-bit well-known community value

        Returns:
            Community instance
        """
        packed = pack('!L', value)
        return cls(packed)

    @property
    def community(self) -> Buffer:
        """Get the packed community bytes (for compatibility)."""
        return self._packed

    def _get_string(self) -> str:
        """Get string representation."""
        if self._packed == self.NO_EXPORT:
            return 'no-export'
        elif self._packed == self.NO_ADVERTISE:
            return 'no-advertise'
        elif self._packed == self.NO_EXPORT_SUBCONFED:
            return 'no-export-subconfed'
        elif self._packed == self.NO_PEER:
            return 'no-peer'
        elif self._packed == self.BLACKHOLE:
            return 'blackhole'
        else:
            return '%d:%d' % unpack('!HH', self._packed)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Community):
            return False
        return self._packed == other._packed

    def __ne__(self, other: object) -> bool:
        if not isinstance(other, Community):
            return True
        return self._packed != other._packed

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, Community):
            raise TypeError(f"'<' not supported between instances of 'Community' and '{type(other).__name__}'")
        return bytes(self._packed) < bytes(other._packed)

    def __le__(self, other: object) -> bool:
        if not isinstance(other, Community):
            raise TypeError(f"'<=' not supported between instances of 'Community' and '{type(other).__name__}'")
        return bytes(self._packed) <= bytes(other._packed)

    def __gt__(self, other: object) -> bool:
        if not isinstance(other, Community):
            raise TypeError(f"'>' not supported between instances of 'Community' and '{type(other).__name__}'")
        return bytes(self._packed) > bytes(other._packed)

    def __ge__(self, other: object) -> bool:
        if not isinstance(other, Community):
            raise TypeError(f"'>=' not supported between instances of 'Community' and '{type(other).__name__}'")
        return bytes(self._packed) >= bytes(other._packed)

    def __hash__(self) -> int:
        return hash(self._packed)

    def json(self) -> str:
        return '[ %d, %d ]' % unpack('!HH', self._packed)

    def pack_attribute(self, negotiated: Negotiated) -> Buffer:
        return self._packed

    def __repr__(self) -> str:
        return self._get_string()

    def __len__(self) -> int:
        return 4

    @classmethod
    def unpack_attribute(cls, data: Buffer, negotiated: Negotiated) -> 'Community':
        return cls.from_packet(data)

    @classmethod
    def cached(cls, packed: Buffer) -> 'Community':
        if not cls.caching:
            return cls(packed)
        # Convert to bytes for hashable cache key (memoryview is not hashable)
        packed_bytes = bytes(packed)
        if packed_bytes in cls.cache:
            return cls.cache[packed_bytes]
        instance = cls(packed_bytes)
        cls.cache[packed_bytes] = instance
        return instance


# Always cache well-known communities, they will be used a lot
if not Community.cache:
    Community.cache[Community.NO_EXPORT] = Community(Community.NO_EXPORT)
    Community.cache[Community.NO_ADVERTISE] = Community(Community.NO_ADVERTISE)
    Community.cache[Community.NO_EXPORT_SUBCONFED] = Community(Community.NO_EXPORT_SUBCONFED)
    Community.cache[Community.NO_PEER] = Community(Community.NO_PEER)
    Community.cache[Community.BLACKHOLE] = Community(Community.BLACKHOLE)
