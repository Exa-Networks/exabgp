"""route.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from exabgp.protocol.family import FamilyTuple

if TYPE_CHECKING:
    from exabgp.bgp.message.update.attribute.collection import AttributeCollection
    from exabgp.bgp.message.update.nlri.nlri import NLRI

from exabgp.bgp.message import Action
from exabgp.protocol.ip import IP


class Route:
    """A Route is an NLRI with attributes and operation context.

    Route is IMMUTABLE after creation. Use with_nexthop() to create modified copies.

    Action (announce vs withdraw) is NOT stored in Route. Instead, action is
    determined by the method called: add_to_rib() for announces, del_from_rib()
    for withdraws. This saves 8 bytes per route.
    """

    __slots__ = ('nlri', 'attributes', '_nexthop', '_Route__index', '_refcount')

    nlri: NLRI
    attributes: AttributeCollection
    _nexthop: IP
    _Route__index: bytes
    _refcount: int

    @staticmethod
    def family_prefix(family: FamilyTuple) -> bytes:
        return b'%02x%02x' % family

    def __init__(
        self,
        nlri: NLRI,
        attributes: AttributeCollection,
        nexthop: IP = IP.NoNextHop,
    ) -> None:
        self.nlri = nlri
        self.attributes = attributes
        self._nexthop = nexthop
        # Index is computed lazily on first .index() call, not at __init__ time.
        # This is intentional: at construction time the NLRI may not be fully populated
        # (e.g., nexthop not yet set), which would cause api-attributes.sequence to fail.
        # The lazy evaluation ensures the index is computed only when all NLRI fields are set.
        # Note: Use mangled name directly for mypy compatibility with __slots__
        self._Route__index = b''
        # Refcount for global route store (tracks how many neighbors reference this route)
        self._refcount = 0

    def ref_inc(self) -> int:
        """Increment reference count. Returns new count."""
        self._refcount += 1
        return self._refcount

    def ref_dec(self) -> int:
        """Decrement reference count. Returns new count."""
        self._refcount -= 1
        return self._refcount

    @property
    def nexthop(self) -> IP:
        """Get the route nexthop.

        Returns self._nexthop directly.
        Route must be created with explicit nexthop= parameter.
        """
        return self._nexthop

    def with_nexthop(self, nexthop: IP) -> 'Route':
        """Return a new Route with a different nexthop.

        Route is immutable, so this creates a new instance.
        """
        return Route(self.nlri, self.attributes, nexthop=nexthop)

    def with_merged_attributes(self, extra_attrs: 'AttributeCollection') -> 'Route':
        """Return a new Route with additional attributes merged in.

        Route is immutable, so this creates a new instance.
        Attributes from extra_attrs are added to this route's attributes.
        Existing attributes in this route take precedence (not overwritten).

        Args:
            extra_attrs: Additional attributes to merge into this route
        """
        from exabgp.bgp.message.update.attribute.collection import AttributeCollection

        merged = AttributeCollection()
        # First add extra attributes
        for code, attr in extra_attrs.items():
            merged.add(attr)
        # Then add our attributes (these take precedence)
        for code, attr in self.attributes.items():
            merged.add(attr)
        return Route(self.nlri, merged, nexthop=self._nexthop)

    def index(self) -> bytes:
        if not self._Route__index:
            self._Route__index = b'%02x%02x' % self.nlri.family().afi_safi() + self.nlri.index()
        return self._Route__index

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Route):
            return False
        return self.nlri == other.nlri and self.attributes == other.attributes

    def __ne__(self, other: object) -> bool:
        if not isinstance(other, Route):
            return True
        return self.nlri != other.nlri or self.attributes != other.attributes

    def __lt__(self, other: object) -> bool:
        raise RuntimeError('comparing Route for ordering does not make sense')

    def __le__(self, other: object) -> bool:
        raise RuntimeError('comparing Route for ordering does not make sense')

    def __gt__(self, other: object) -> bool:
        raise RuntimeError('comparing Route for ordering does not make sense')

    def __ge__(self, other: object) -> bool:
        raise RuntimeError('comparing Route for ordering does not make sense')

    def extensive(self) -> str:
        # If you change this you must change as well extensive in Update
        # nexthop comes from Route, not NLRI (NLRI.extensive() no longer includes nexthop)
        nexthop_str = '' if self._nexthop is IP.NoNextHop else f' next-hop {self._nexthop}'
        return f'{self.nlri!s}{nexthop_str}{self.attributes!s}'

    def __repr__(self) -> str:
        return self.extensive()

    def feedback(self, action: Action) -> str:
        """Validate route constraints and return error message if invalid.

        Args:
            action: ANNOUNCE or WITHDRAW - determines validation rules

        Returns:
            Empty string if valid, error message if invalid.
        """
        if self.nlri is None:
            return 'route has no nlri'
        # Route handles nexthop validation (nexthop is stored in Route, not NLRI)
        if self._nexthop is IP.NoNextHop and action == Action.ANNOUNCE:
            return f'{self.nlri.safi.name()} nlri next-hop missing'
        # Delegate NLRI-specific validation
        return self.nlri.feedback(action)
