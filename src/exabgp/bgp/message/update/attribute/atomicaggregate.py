"""atomicaggregate.py

Created by Thomas Mangin on 2012-07-14.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from exabgp.util.types import Buffer
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from exabgp.bgp.message.open.capability.negotiated import Negotiated

from exabgp.bgp.message.update.attribute.attribute import Attribute

# ========================================================== AtomicAggregate (6)
#


@Attribute.register()
class AtomicAggregate(Attribute):
    ID = Attribute.CODE.ATOMIC_AGGREGATE
    FLAG = Attribute.Flag.TRANSITIVE
    CACHING = True
    DISCARD = True
    VALID_ZERO = True

    def __init__(self, packed: Buffer) -> None:
        """Initialize AtomicAggregate from packed wire-format bytes.

        NO validation - trusted internal use only.
        Use from_packet() for wire data or make_atomic_aggregate() for semantic construction.

        Args:
            packed: Raw attribute value bytes (must be empty for AtomicAggregate)
        """
        self._packed: Buffer = packed

    @classmethod
    def from_packet(cls, data: Buffer) -> 'AtomicAggregate':
        """Validate and create from wire-format bytes.

        Args:
            data: Raw attribute value bytes from wire

        Returns:
            AtomicAggregate instance

        Raises:
            ValueError: If data is not empty
        """
        if data:
            raise ValueError(f'AtomicAggregate must be empty, got {len(data)} bytes')
        return cls(data)

    @classmethod
    def make_atomic_aggregate(cls) -> 'AtomicAggregate':
        """Create AtomicAggregate.

        Returns:
            AtomicAggregate instance
        """
        return cls(b'')

    # Inherited from Attribute
    # def __eq__ (self, other):
    # def __ne__ (self, other):

    def pack_attribute(self, negotiated: Negotiated | None = None) -> bytes:
        return self._attribute(self._packed)

    def __len__(self) -> int:
        return len(self._packed)

    def __bool__(self) -> bool:
        # AtomicAggregate is always truthy (flag attribute with no payload)
        # Override because _packed is always empty, making len() return 0
        return True

    def __repr__(self) -> str:
        return ''

    def __hash__(self) -> int:
        return 0

    @classmethod
    def unpack_attribute(cls, data: Buffer, negotiated: Negotiated) -> AtomicAggregate:
        # Wire data - use from_packet for validation
        return cls.from_packet(data)

    @classmethod
    def setCache(cls) -> None:
        # There can only be one, build it now :)
        cls.cache[Attribute.CODE.ATOMIC_AGGREGATE][''] = cls.make_atomic_aggregate()


AtomicAggregate.setCache()
