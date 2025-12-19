"""rib/__init__.py

Created by Thomas Mangin on 2010-01-15.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from typing import ClassVar

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

    def __init__(
        self,
        name: str,
        adj_rib_in: bool,
        adj_rib_out: bool,
        families: set[FamilyTuple],
        enabled: bool = True,
    ) -> None:
        self.name = name
        self.enabled = enabled

        if name not in self._cache:
            self.incoming = IncomingRIB(adj_rib_in, families, enabled)
            self.outgoing = OutgoingRIB(adj_rib_out, families, enabled)
            self._cache[name] = self
            return

        self.incoming = self._cache[name].incoming
        self.outgoing = self._cache[name].outgoing
        self.incoming.families = families
        self.outgoing.families = families
        self.outgoing.delete_cached_family(families)

        if not adj_rib_out:
            self.outgoing.clear()
        if not adj_rib_in:
            self.incoming.clear()

    def enable(self, new_name: str, adj_rib_in: bool, adj_rib_out: bool, families: set[FamilyTuple]) -> None:
        """Enable a disabled RIB with proper name and settings."""
        # Remove old placeholder from cache
        old_name = self.name
        if old_name in self._cache:
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
        self.outgoing.reset()

    def uncache(self) -> None:
        if self.name in self._cache:
            del self._cache[self.name]

    # This code was never tested ...
    def clear(self) -> None:
        families = self._cache[self.name].incoming.families
        self._cache[self.name].incoming = IncomingRIB(self.incoming.cache, families, self.enabled)
        self._cache[self.name].outgoing = OutgoingRIB(self.outgoing.cache, families, self.enabled)
