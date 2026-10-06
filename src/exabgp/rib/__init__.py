"""rib/__init__.py

Created by Thomas Mangin on 2010-01-15.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from copy import deepcopy
from typing import ClassVar, Self

from exabgp.rib.incoming import IncomingRIB
from exabgp.rib.outgoing import OutgoingRIB
from exabgp.protocol.family import FamilyTuple


class RIB:
    # when we perform a configuration reload using SIGUSR, we must not use the RIB
    # without the cache, all the updates previously sent via the API are lost

    _cache: ClassVar[dict[str, RIB]] = {}

    name: str
    enabled: bool
    incoming: IncomingRIB
    outgoing: OutgoingRIB

    def __init__(self, name: str, enabled: bool, incoming: IncomingRIB, outgoing: OutgoingRIB) -> None:
        self.name = name
        self.enabled = enabled
        self.incoming = incoming
        self.outgoing = outgoing

    @classmethod
    def make_rib(
        cls,
        name: str,
        adj_rib_in: bool,
        adj_rib_out: bool,
        families: set[FamilyTuple],
        enabled: bool = True,
    ) -> RIB:
        """The RIB of this name: a new one, or the tables the cache kept for it across a reload."""
        if name not in cls._cache:
            incoming = IncomingRIB(adj_rib_in, families, enabled)
            outgoing = OutgoingRIB(adj_rib_out, families, enabled)
            outgoing.membership = incoming
            rib = cls(name, enabled, incoming, outgoing)
            cls._cache[name] = rib
            return rib

        cached = cls._cache[name]
        rib = cls(name, enabled, cached.incoming, cached.outgoing)
        rib.incoming.families = families
        rib.outgoing.families = families
        rib.outgoing.delete_cached_family(families)

        if not adj_rib_out:
            rib.outgoing.clear()
        if not adj_rib_in:
            rib.incoming.clear()
        return rib

    # A copy has its own tables and is not in the cache: built by __init__, which does not
    # touch the cache, as copy's generic path cannot build a compiled class (plan/wip-mypyc.md)
    def __deepcopy__(self, memo: dict[int, object]) -> Self:
        copied = type(self)(self.name, self.enabled, deepcopy(self.incoming, memo), deepcopy(self.outgoing, memo))
        memo[id(self)] = copied
        return copied

    def enable(self, new_name: str, adj_rib_in: bool, adj_rib_out: bool, families: set[FamilyTuple]) -> None:
        """Enable a disabled RIB with proper name and settings."""
        # Remove our placeholder from the cache. Only ours: a deep copy carries the name of the
        # RIB it was copied from, and the entry under that name belongs to the original
        old_name = self.name
        if self._cache.get(old_name) is self:
            del self._cache[old_name]

        # Update name and enabled state
        self.name = new_name
        self.enabled = True

        # Check if a RIB with this name already exists in cache (reload scenario)
        if new_name in self._cache:
            # Reuse the cached RIB's incoming/outgoing to preserve state
            cached_rib = self._cache[new_name]
            self.incoming = cached_rib.incoming
            self.outgoing = cached_rib.outgoing
            self.incoming.enabled = True
            self.outgoing.enabled = True
            self.incoming.families = families
            self.outgoing.families = families
            self.outgoing.delete_cached_family(families)

            if not adj_rib_out:
                self.outgoing.clear()
            if not adj_rib_in:
                self.incoming.clear()
        else:
            # No cached RIB - enable our own incoming/outgoing
            self.incoming.enabled = True
            self.outgoing.enabled = True
            self.incoming.families = families
            self.outgoing.families = families
            self.incoming.cache = adj_rib_in
            self.outgoing.cache = adj_rib_out

        # Add/update cache with new name
        self._cache[new_name] = self

    def reset(self) -> None:
        self.incoming.reset()
        self.outgoing.session_reset()

    def uncache(self) -> None:
        if self.name in self._cache:
            del self._cache[self.name]

    # This code was never tested ...
    def clear(self) -> None:
        families = self._cache[self.name].incoming.families
        self._cache[self.name].incoming = IncomingRIB(self.incoming.cache, families, self.enabled)
        self._cache[self.name].outgoing = OutgoingRIB(self.outgoing.cache, families, self.enabled)
        self._cache[self.name].outgoing.membership = self._cache[self.name].incoming
