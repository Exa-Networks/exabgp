"""store.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Iterator, overload

from exabgp.bgp.message import Action
from exabgp.protocol.ip import IP

if TYPE_CHECKING:
    from exabgp.rib.route import Route
    from exabgp.bgp.message.update.nlri.nlri import NLRI
    from exabgp.bgp.message.update.attribute.collection import AttributeCollection
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
        # Use route.action (not nlri.action) to support transition from nlri.action to route._action
        if route.action == Action.UNSET:
            raise RuntimeError(f'NLRI action is UNSET (not set to ANNOUNCE or WITHDRAW): {route.nlri}')
        if route.action == Action.WITHDRAW:
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

    # add a route to the cache of seen Route
    @overload
    def update_cache(self, route: 'Route') -> None: ...
    @overload
    def update_cache(self, nlri: 'NLRI', attributes: 'AttributeCollection') -> None: ...
    @overload
    def update_cache(self, nlri: 'NLRI', attributes: 'AttributeCollection', action: int) -> None: ...
    @overload
    def update_cache(self, nlri: 'NLRI', attributes: 'AttributeCollection', action: int, nexthop: IP) -> None: ...

    def update_cache(
        self,
        route_or_nlri: 'Route | NLRI',
        attributes: 'AttributeCollection | None' = None,
        action: int | None = None,
        nexthop: IP | None = None,
    ) -> None:
        if not self.enabled or not self.cache:
            return

        # Handle signatures: (route) or (nlri, attributes[, action[, nexthop]])
        if attributes is None:
            # Legacy signature: update_cache(route) - uses route.action and route.nexthop
            route = route_or_nlri
            nlri = route.nlri
            attrs = route.attributes
            family = nlri.family().afi_safi()
            index = route.index()
            actual_action = route.action
            actual_nexthop = route.nexthop
        else:
            # New signature: update_cache(nlri, attributes[, action[, nexthop]])
            nlri = route_or_nlri
            attrs = attributes
            family = nlri.family().afi_safi()
            index = self._make_index(nlri)
            # Use explicit action if provided, otherwise fall back to nlri.action
            actual_action = action if action is not None else nlri.action
            # Use explicit nexthop if provided, otherwise use NoNextHop
            actual_nexthop = nexthop if nexthop is not None else IP.NoNextHop

        if actual_action == Action.UNSET:
            raise RuntimeError(f'NLRI action is UNSET (not set to ANNOUNCE or WITHDRAW): {nlri}')
        if actual_action == Action.ANNOUNCE:
            # Store as Route for backward compatibility with cached_routes()
            from exabgp.rib.route import Route

            self._seen.setdefault(family, {})[index] = Route(nlri, attrs, Action.ANNOUNCE, nexthop=actual_nexthop)
        elif family in self._seen:
            self._seen[family].pop(index, None)

    # remove a route from cache (for withdrawals without modifying nlri.action)
    @overload
    def update_cache_withdraw(self, route: 'Route') -> None: ...
    @overload
    def update_cache_withdraw(self, nlri: 'NLRI', attributes: 'AttributeCollection | None' = None) -> None: ...

    def update_cache_withdraw(
        self, route_or_nlri: 'Route | NLRI', attributes: 'AttributeCollection | None' = None
    ) -> None:
        if not self.enabled or not self.cache:
            return

        # Handle both signatures
        if attributes is None and hasattr(route_or_nlri, 'index') and callable(route_or_nlri.index):
            # Check if it's a Route object (has index() method that returns bytes)
            try:
                route = route_or_nlri
                family = route.nlri.family().afi_safi()
                index = route.index()
            except AttributeError:
                # It's an NLRI
                nlri = route_or_nlri
                family = nlri.family().afi_safi()
                index = self._make_index(nlri)
        else:
            # New signature: (nlri, attributes) - attributes ignored for withdraw
            nlri = route_or_nlri
            family = nlri.family().afi_safi()
            index = self._make_index(nlri)

        if family in self._seen:
            self._seen[family].pop(index, None)
