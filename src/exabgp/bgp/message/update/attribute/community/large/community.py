"""Support for RFC 8092

Copyright (c) 2016 Job Snijders <job@ntt.net>
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from struct import pack, unpack
from typing import TYPE_CHECKING, ClassVar

if TYPE_CHECKING:
    from exabgp.bgp.message.open.capability.negotiated import Negotiated

from exabgp.bgp.message.update.attribute import Attribute
from exabgp.util.types import Buffer


class LargeCommunity(Attribute):
    """Large BGP Community (RFC 8092).

    Stores packed wire-format bytes (12 bytes).
    """

    MAX: ClassVar[int] = 0xFFFFFFFFFFFFFFFFFFFFFFFF

    _instance_cache: ClassVar[dict[bytes, LargeCommunity]] = {}
    caching: ClassVar[bool] = True

    def __init__(self, packed: Buffer) -> None:
        """Initialize from packed wire-format bytes.

        NO validation - trusted internal use only.
        Use from_packet() for wire data or make_large_community() for semantic construction.

        Args:
            packed: Raw large community bytes (12 bytes)
        """
        self._packed: Buffer = packed

    @classmethod
    def from_packet(cls, data: Buffer) -> 'LargeCommunity':
        """Validate and create from wire-format bytes.

        Args:
            data: Raw large community bytes from wire

        Returns:
            LargeCommunity instance

        Raises:
            ValueError: If data length is not 12
        """
        if len(data) != 12:
            raise ValueError(f'LargeCommunity must be 12 bytes, got {len(data)}')
        return cls(data)

    @classmethod
    def make_large_community(cls, global_admin: int, local_data1: int, local_data2: int) -> 'LargeCommunity':
        """Create from global administrator and local data values.

        Args:
            global_admin: 32-bit global administrator
            local_data1: 32-bit local data 1
            local_data2: 32-bit local data 2

        Returns:
            LargeCommunity instance
        """
        packed = pack('!LLL', global_admin, local_data1, local_data2)
        return cls(packed)

    @property
    def large_community(self) -> Buffer:
        """Get the packed large community bytes (for compatibility)."""
        return self._packed

    def _get_string(self) -> str:
        """Get string representation."""
        return '%d:%d:%d' % unpack('!LLL', self._packed)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, LargeCommunity):
            return False
        return self._packed == other._packed

    def __ne__(self, other: object) -> bool:
        if not isinstance(other, LargeCommunity):
            return True
        return self._packed != other._packed

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, LargeCommunity):
            raise TypeError(f"'<' not supported between instances of 'LargeCommunity' and '{type(other).__name__}'")
        return bytes(self._packed) < bytes(other._packed)

    def __le__(self, other: object) -> bool:
        if not isinstance(other, LargeCommunity):
            raise TypeError(f"'<=' not supported between instances of 'LargeCommunity' and '{type(other).__name__}'")
        return bytes(self._packed) <= bytes(other._packed)

    def __gt__(self, other: object) -> bool:
        if not isinstance(other, LargeCommunity):
            raise TypeError(f"'>' not supported between instances of 'LargeCommunity' and '{type(other).__name__}'")
        return bytes(self._packed) > bytes(other._packed)

    def __ge__(self, other: object) -> bool:
        if not isinstance(other, LargeCommunity):
            raise TypeError(f"'>=' not supported between instances of 'LargeCommunity' and '{type(other).__name__}'")
        return bytes(self._packed) >= bytes(other._packed)

    def __hash__(self) -> int:
        return hash(self._packed)

    def json(self) -> str:
        return '[ %d, %d , %d ]' % unpack('!LLL', self._packed)

    def pack_attribute(self, negotiated: Negotiated) -> Buffer:
        return self._packed

    def __repr__(self) -> str:
        return self._get_string()

    def __len__(self) -> int:
        return 12

    @classmethod
    def unpack_attribute(cls, data: Buffer, negotiated: Negotiated) -> 'LargeCommunity':
        return cls.from_packet(data)

    @classmethod
    def cached(cls, packed: Buffer) -> 'LargeCommunity':
        if not cls.caching:
            return cls(packed)
        if packed in cls._instance_cache:
            return cls._instance_cache[packed]
        instance = cls(packed)
        cls._instance_cache[packed] = instance
        return instance
