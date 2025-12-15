"""store.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Iterator

if TYPE_CHECKING:
    from exabgp.rib.route import Route
    from exabgp.bgp.message.update.nlri.nlri import NLRI
    from exabgp.protocol.family import AFI, SAFI


class Cache:
    cache: bool
    enabled: bool
    families: set[tuple[AFI, SAFI]]
    _seen: dict[tuple[AFI, SAFI], dict[bytes, Route]]

    def __init__(self, cache: bool, families: set[tuple[AFI, SAFI]], enabled: bool = True) -> None:
        self.cache = cache
        self.enabled = enabled
        self._seen = {}
        # self._seen[family][route-index] = route
        # nlri.index() would be a few bytes shorter than route.index() but ..
        # we need route.index() in other part of the code
        # we pre-compute route.index() so that it is only allocted once
        self.families = families

    def clear_cache(self) -> None:
        self._seen = {}

    def delete_cached_family(self, families: set[tuple[AFI, SAFI]]) -> None:
        for family in list(self._seen.keys()):
            if family not in families:
                del self._seen[family]

    def cached_routes(
        self,
        families: list[tuple[AFI, SAFI]] | None = None,
    ) -> Iterator['Route']:
        """Yield all cached routes (announces only).

        Cache only stores announced routes. Withdraws remove routes from cache.
        """
        if not self.enabled:
            return
        # families can be None or []
        requested_families = self.families if families is None else set(families).intersection(self.families)

        # we use list() to make a snapshot of the data at the time we run the command
        for family in requested_families:
            for route in list(self._seen.get(family, {}).values()):
                yield route

    def in_cache(self, route: 'Route') -> bool:
        """Check if route is already in cache (for announce deduplication).

        Only used from add_to_rib() which handles announces.
        """
        if not self.enabled or not self.cache:
            return False

        cached = self._seen.get(route.nlri.family().afi_safi(), {}).get(route.index(), None)
        if not cached:
            return False

        if cached.attributes.index() != route.attributes.index():
            return False

        # Use route.nexthop (nexthop is stored in Route, not NLRI)
        # Use getattr for safety since some NLRIs may not have nexthop
        try:
            cached_nh = cached.nexthop
            route_nh = route.nexthop
            if cached_nh.index() != route_nh.index():
                return False
        except AttributeError:
            pass  # NLRI type without nexthop

        return True

    @staticmethod
    def _make_index(nlri: 'NLRI') -> bytes:
        """Compute cache index for an NLRI (family prefix + nlri index)."""
        return b'%02x%02x' % nlri.family().afi_safi() + nlri.index()

    def update_cache(self, route: 'Route') -> None:
        """Add announced route to cache.

        Only used from _update_rib() which handles announces.
        For withdraws, use update_cache_withdraw().
        """
        if not self.enabled or not self.cache:
            return

        nlri = route.nlri
        family = nlri.family().afi_safi()
        index = route.index()

        # Store route in cache (announces only)
        self._seen.setdefault(family, {})[index] = route

    # remove a route from cache (for withdrawals)
    def update_cache_withdraw(self, nlri: 'NLRI') -> None:
        if not self.enabled or not self.cache:
            return

        family = nlri.family().afi_safi()
        index = self._make_index(nlri)

        if family in self._seen:
            self._seen[family].pop(index, None)
