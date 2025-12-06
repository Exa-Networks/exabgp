"""store.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Iterator, overload

from exabgp.bgp.message import Action

if TYPE_CHECKING:
    from exabgp.rib.route import Route
    from exabgp.bgp.message.update.nlri.nlri import NLRI
    from exabgp.bgp.message.update.attribute.attributes import AttributeSet
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
        actions: tuple[int, ...] = (Action.ANNOUNCE,),
    ) -> Iterator['Route']:
        if not self.enabled:
            return
        # families can be None or []
        requested_families = self.families if families is None else set(families).intersection(self.families)

        # we use list() to make a snapshot of the data at the time we run the command
        # Note: The cache only stores announces (withdraws are removed), so the action
        # filter is effectively a no-op but kept for backward compatibility
        for family in requested_families:
            for route in list(self._seen.get(family, {}).values()):
                # Cache only stores announces, but check action for backward compat
                # Once nlri.action is removed, this filter can be removed too
                if Action.ANNOUNCE in actions:
                    yield route

    def in_cache(self, route: 'Route') -> bool:
        if not self.enabled or not self.cache:
            return False

        # Withdraws are never duplicates - they always need to be processed
        if route.nlri.action == Action.WITHDRAW:
            return False

        cached = self._seen.get(route.nlri.family().afi_safi(), {}).get(route.index(), None)
        if not cached:
            return False

        if cached.attributes.index() != route.attributes.index():
            return False

        cached_nh = getattr(cached.nlri, 'nexthop', None)
        route_nh = getattr(route.nlri, 'nexthop', None)
        if cached_nh is not None and route_nh is not None:
            if cached_nh.index() != route_nh.index():
                return False

        return True

    @staticmethod
    def _make_index(nlri: 'NLRI') -> bytes:
        """Compute cache index for an NLRI (family prefix + nlri index)."""
        return b'%02x%02x' % nlri.family().afi_safi() + nlri.index()

    # add a route to the cache of seen Route
    @overload
    def update_cache(self, route: 'Route') -> None: ...
    @overload
    def update_cache(self, nlri: 'NLRI', attributes: 'AttributeSet') -> None: ...
    @overload
    def update_cache(self, nlri: 'NLRI', attributes: 'AttributeSet', action: int) -> None: ...

    def update_cache(
        self,
        route_or_nlri: 'Route | NLRI',
        attributes: 'AttributeSet | None' = None,
        action: int | None = None,
    ) -> None:
        if not self.enabled or not self.cache:
            return

        # Handle signatures: (route) or (nlri, attributes) or (nlri, attributes, action)
        if attributes is None:
            # Legacy signature: update_cache(route) - uses nlri.action
            route = route_or_nlri  # type: ignore[assignment]
            nlri = route.nlri
            attrs = route.attributes
            family = nlri.family().afi_safi()
            index = route.index()
            # For legacy callers, still read from nlri.action
            actual_action = nlri.action
        else:
            # New signature: update_cache(nlri, attributes[, action])
            nlri = route_or_nlri  # type: ignore[assignment]
            attrs = attributes
            family = nlri.family().afi_safi()
            index = self._make_index(nlri)
            # Use explicit action if provided, otherwise fall back to nlri.action
            actual_action = action if action is not None else nlri.action

        if actual_action == Action.ANNOUNCE:
            # Store as Route for backward compatibility with cached_routes()
            from exabgp.rib.route import Route

            self._seen.setdefault(family, {})[index] = Route(nlri, attrs)
        elif family in self._seen:
            self._seen[family].pop(index, None)

    # remove a route from cache (for withdrawals without modifying nlri.action)
    @overload
    def update_cache_withdraw(self, route: 'Route') -> None: ...
    @overload
    def update_cache_withdraw(self, nlri: 'NLRI', attributes: 'AttributeSet | None' = None) -> None: ...

    def update_cache_withdraw(self, route_or_nlri: 'Route | NLRI', attributes: 'AttributeSet | None' = None) -> None:
        if not self.enabled or not self.cache:
            return

        # Handle both signatures
        if attributes is None and hasattr(route_or_nlri, 'index') and callable(route_or_nlri.index):
            # Check if it's a Route object (has index() method that returns bytes)
            try:
                route = route_or_nlri  # type: ignore[assignment]
                family = route.nlri.family().afi_safi()
                index = route.index()
            except AttributeError:
                # It's an NLRI
                nlri = route_or_nlri  # type: ignore[assignment]
                family = nlri.family().afi_safi()
                index = self._make_index(nlri)
        else:
            # New signature: (nlri, attributes) - attributes ignored for withdraw
            nlri = route_or_nlri  # type: ignore[assignment]
            family = nlri.family().afi_safi()
            index = self._make_index(nlri)

        if family in self._seen:
            self._seen[family].pop(index, None)
