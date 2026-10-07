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
        rib._reconfigure(adj_rib_in, adj_rib_out, families)
        return rib

    def _reconfigure(self, adj_rib_in: bool, adj_rib_out: bool, families: set[FamilyTuple]) -> None:
        """Apply a reloaded configuration to the tables the cache kept for this name."""
        self.incoming.families = families
        self.outgoing.families = families
        self.outgoing.delete_cached_family(families)

        if not adj_rib_out:
            self.outgoing.clear()
        if not adj_rib_in:
            self.incoming.clear()
        # The switches are the new configuration's, not those the tables were first built with
        self.incoming.cache = adj_rib_in
        self.outgoing.cache = adj_rib_out

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
            self._reconfigure(adj_rib_in, adj_rib_out, families)
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

    def clear(self) -> None:
        """Start this RIB again with empty tables.

        Our own tables, not those of the cache entry under our name: a deep copy carries the
        name of the RIB it was copied from, and that entry belongs to the original. A RIB
        built by make_rib() on a reload shares its tables with the cache entry, which then
        takes the new ones too, so the next reload does not bring the old routes back.
        """
        families = self.incoming.families
        cached = self._cache.get(self.name)
        shared = cached is not None and cached.incoming is self.incoming and cached.outgoing is self.outgoing
        self.incoming = IncomingRIB(self.incoming.cache, families, self.enabled)
        self.outgoing = OutgoingRIB(self.outgoing.cache, families, self.enabled)
        self.outgoing.membership = self.incoming
        if shared:
            assert cached is not None
            cached.incoming = self.incoming
            cached.outgoing = self.outgoing
