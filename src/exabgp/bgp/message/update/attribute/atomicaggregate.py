"""atomicaggregate.py

Created by Thomas Mangin on 2012-07-14.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from exabgp.bgp.message.open.capability.negotiated import Negotiated

from exabgp.bgp.message.update.attribute.attribute import Attribute
from exabgp.bgp.message.notification import Notify


# ========================================================== AtomicAggregate (6)
#


@Attribute.register()
class AtomicAggregate(Attribute):
    ID = Attribute.CODE.ATOMIC_AGGREGATE
    FLAG = Attribute.Flag.TRANSITIVE
    CACHING = True
    DISCARD = True
    VALID_ZERO = True

    def __init__(self, packed: bytes = b'') -> None:
        """Initialize AtomicAggregate from packed wire-format bytes.

        Args:
            packed: Raw attribute value bytes (must be empty for AtomicAggregate)
        """
        self._packed: bytes = packed

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
        # AtomicAggregate is always 0 bytes payload + 3 byte header = 3 bytes total
        return 3

    def __repr__(self) -> str:
        return ''

    def __hash__(self) -> int:
        return 0

    @classmethod
    def unpack_attribute(cls, data: bytes, negotiated: Negotiated) -> AtomicAggregate:
        if data:
            raise Notify(3, 2, 'invalid ATOMIC_AGGREGATE %s' % [hex(_) for _ in data])
        return cls(data)

    @classmethod
    def setCache(cls) -> None:
        # There can only be one, build it now :)
        cls.cache[Attribute.CODE.ATOMIC_AGGREGATE][''] = cls.make_atomic_aggregate()


AtomicAggregate.setCache()
