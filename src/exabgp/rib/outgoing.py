"""store.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Iterator, overload

from exabgp.bgp.message import Action, UpdateCollection
from exabgp.bgp.message.refresh import RouteRefresh
from exabgp.logger import lazymsg, log
from exabgp.protocol.family import AFI, SAFI
from exabgp.rib.cache import Cache

if TYPE_CHECKING:
    from exabgp.bgp.message.update.attribute.collection import AttributeCollection
    from exabgp.bgp.message.update.nlri.nlri import NLRI
    from exabgp.protocol.family import AFI, SAFI
    from exabgp.rib.route import Route

# This is needs to be an ordered dict
RIBdict = dict


class OutgoingRIB(Cache):
    _watchdog: dict[str, dict[str, dict[bytes, Route]]]
    _new_nlri: dict[bytes, Route]
    _new_attr_af_nlri: dict[bytes, dict[tuple[AFI, SAFI], dict[bytes, Route]]]
    _new_attribute: dict[bytes, AttributeCollection]
    _refresh_families: set[tuple[AFI, SAFI]]
    _refresh_routes: list[Route]

    # New structure for withdraws - avoids deepcopy by not modifying nlri.action
    # Indexed by family -> nlri_index -> (NLRI, AttributeCollection)
    _pending_withdraws: dict[tuple[AFI, SAFI], dict[bytes, tuple['NLRI', 'AttributeCollection']]]

    def __init__(self, cache: bool, families: set[tuple[AFI, SAFI]], enabled: bool = True) -> None:
        Cache.__init__(self, cache, families, enabled)

        self._watchdog = {}
        self.families = families

        # using route-index and not nlri-index as it is cached as same us memory
        # even if it is a few bytes longer
        self._new_nlri = {}  # self._new_nlri[route-index] = route
        self._new_attr_af_nlri = {}  # self._new_attr_af_nlri[attr-index][family][route-index] = route
        self._new_attribute = {}  # self._new_attribute[attr-index] = attributes

        # _new_nlri: we are modifying this nlri
        # this is useful to iterate and find nlri currently handled

        # _new_attr_af_nlri: add or remove the nlri
        # this is the best way to iterate over NLRI when generating updates
        # sharing attributes, then family

        # _new_attribute: attributes of one of the routes
        # makes our life easier, but could be removed

        # Separate storage for withdraws - indexed by family, then nlri_index
        # This avoids needing to deepcopy and modify nlri.action
        self._pending_withdraws = {}

        self._refresh_families = set()
        self._refresh_routes = []

        # Flush callbacks for sync mode - fire when updates() exhausts
        self._flush_callbacks: list[asyncio.Event] = []

        self.reset()

    # will resend all the routes once we reconnect
    def reset(self) -> None:
        # WARNING : this function can run while we are in the updates() loop too !
        self._refresh_families = set()
        self._refresh_routes = []
        for _ in self.updates(True):
            pass

    # back to square one, all the routes are removed
    def clear(self) -> None:
        self.clear_cache()
        self._new_nlri = {}
        self._new_attr_af_nlri = {}
        self._new_attribute = {}
        self._pending_withdraws = {}
        self.reset()

    def pending(self) -> bool:
        if not self.enabled:
            return False
        return len(self._new_nlri) != 0 or len(self._refresh_routes) != 0 or len(self._pending_withdraws) != 0

    def register_flush_callback(self) -> asyncio.Event:
        """Register callback to be fired when RIB is flushed to wire.

        Returns an asyncio.Event that will be set when updates() generator exhausts.
        Used by sync mode API commands to wait for routes to be sent on wire.
        """
        event = asyncio.Event()
        self._flush_callbacks.append(event)
        log.debug(lazymsg('rib.flush.callback.registered total={n}', n=len(self._flush_callbacks)), 'rib')
        return event

    def fire_flush_callbacks(self) -> None:
        """Fire all registered flush callbacks.

        Called when updates() generator exhausts (all routes sent to wire).
        Sets all registered events and clears the callback list.
        """
        if self._flush_callbacks:
            log.debug(lazymsg('rib.flush.callbacks.firing count={n}', n=len(self._flush_callbacks)), 'rib')
            for event in self._flush_callbacks:
                event.set()
            self._flush_callbacks.clear()

    def resend(self, enhanced_refresh: bool, family: tuple[AFI, SAFI] | None = None) -> None:
        if not self.enabled:
            return
        requested_families = set(self.families)

        if family is not None:
            requested_families = set(self.families).intersection([family])

        if enhanced_refresh:
            for family in requested_families:
                self._refresh_families.add(family)

        for route in self.cached_routes(list(requested_families)):
            self._refresh_routes.append(route)

    def withdraw(self, families: set[tuple[AFI, SAFI]] | None = None) -> None:
        if not self.enabled:
            return
        if not families:
            families = self.families
        requested_families = set(families).intersection(self.families)

        routes = list(self.cached_routes(list(requested_families), (Action.ANNOUNCE, Action.WITHDRAW)))
        for route in routes:
            self.del_from_rib(route)

    def queued_routes(self) -> Iterator[Route]:
        if not self.enabled:
            return
        for route in self._new_nlri.values():
            yield route

    def replace_restart(self, previous: list[Route], new: list[Route]) -> None:
        if not self.enabled:
            return
        # this requires that all routes are announcements
        indexed: dict[bytes, Route] = {}

        for route in previous:
            indexed[route.index()] = route

        for route in new:
            indexed.pop(route.index(), None)

        for route in self.cached_routes(list(self.families)):
            self.add_to_rib(route, True)

        for index in list(indexed):
            self.del_from_rib(indexed.pop(index))

    def replace_reload(self, previous: list[Route], new: list[Route]) -> None:
        if not self.enabled:
            return
        # this requires that all routes are announcements
        indexed: dict[bytes, Route] = {}

        for route in previous:
            indexed[route.index()] = route

        for route in new:
            if indexed.pop(route.index(), None) is None:
                self.add_to_rib(route, True)
                continue

        for index in list(indexed):
            self.del_from_rib(indexed.pop(index))

    def add_to_rib_watchdog(self, route: Route) -> bool:
        if not self.enabled:
            return False
        watchdog = route.attributes.watchdog()
        withdraw = route.attributes.withdraw()
        if watchdog:
            name = watchdog.name
            if withdraw:
                self._watchdog.setdefault(name, {}).setdefault('-', {})[route.index()] = route
                return True
            self._watchdog.setdefault(name, {}).setdefault('+', {})[route.index()] = route
        self.add_to_rib(route)
        return True

    def announce_watchdog(self, watchdog: str) -> None:
        if not self.enabled:
            return
        if watchdog in self._watchdog:
            for route in list(self._watchdog[watchdog].get('-', {}).values()):
                route.nlri.action = Action.ANNOUNCE  # pylint: disable=E1101
                self.add_to_rib(route)
                self._watchdog[watchdog].setdefault('+', {})[route.index()] = route
                self._watchdog[watchdog]['-'].pop(route.index())

    def withdraw_watchdog(self, watchdog: str) -> None:
        if not self.enabled:
            return
        if watchdog in self._watchdog:
            for route in list(self._watchdog[watchdog].get('+', {}).values()):
                self.del_from_rib(route)
                self._watchdog[watchdog].setdefault('-', {})[route.index()] = route
                self._watchdog[watchdog]['+'].pop(route.index())

    @overload
    def del_from_rib(self, route: 'Route') -> None: ...
    @overload
    def del_from_rib(self, nlri: 'NLRI', attributes: 'AttributeCollection | None' = None) -> None: ...

    def del_from_rib(self, route_or_nlri: 'Route | NLRI', attributes: 'AttributeCollection | None' = None) -> None:
        if not self.enabled:
            return
        # Handle both signatures: (route) or (nlri, attributes)
        if attributes is None and hasattr(route_or_nlri, 'attributes'):
            # Legacy signature: del_from_rib(route)
            route = route_or_nlri
            nlri = route.nlri
            attrs = route.attributes
            route_index = route.index()
        else:
            # New signature: del_from_rib(nlri, attributes)
            nlri = route_or_nlri
            attrs = attributes
            route_index = self._make_index(nlri)

        log.debug(lazymsg('rib.remove nlri={nlri}', nlri=nlri), 'rib')

        route_family = nlri.family().afi_safi()
        nlri_index = nlri.index()

        attr_af_nlri = self._new_attr_af_nlri
        new_nlri = self._new_nlri

        # remove previous announcement if cancelled/replaced before being sent
        prev_route = new_nlri.get(route_index, None)
        if prev_route:
            prev_route_index = prev_route.index()
            prev_route_attr_index = prev_route.attributes.index()
            attr_af_nlri.setdefault(prev_route_attr_index, {}).setdefault(route_family, RIBdict({})).pop(
                prev_route_index,
                None,
            )
            # Also remove from _new_nlri since we're withdrawing it
            new_nlri.pop(route_index, None)

        # Store withdraw in separate structure - no deepcopy needed!
        # Store (NLRI, AttributeCollection) tuple, action is determined by which dict it's in
        from exabgp.bgp.message.update.attribute.collection import AttributeCollection as AttrsClass

        self._pending_withdraws.setdefault(route_family, {})[nlri_index] = (nlri, attrs if attrs else AttrsClass())

        # Update cache to remove the announced route
        self.update_cache_withdraw(nlri)

    def add_to_resend(self, route: Route) -> None:
        if not self.enabled:
            return
        self._refresh_routes.append(route)

    @overload
    def add_to_rib(self, route: 'Route', force: bool = False) -> None: ...
    @overload
    def add_to_rib(self, nlri: 'NLRI', attributes: 'AttributeCollection', force: bool = False) -> None: ...

    def add_to_rib(
        self,
        route_or_nlri: 'Route | NLRI',
        attributes_or_force: 'AttributeCollection | bool' = False,
        force: bool = False,
    ) -> None:
        if not self.enabled:
            return
        from exabgp.rib.route import Route

        # Handle both signatures: (route, force) or (nlri, attributes, force)
        if isinstance(attributes_or_force, bool):
            # Legacy signature: add_to_rib(route, force=False)
            route = route_or_nlri
            # Support both positional and keyword force: add_to_rib(route, True) or add_to_rib(route, force=True)
            force = attributes_or_force or force
        else:
            # New signature: add_to_rib(nlri, attributes, force=False)
            nlri = route_or_nlri
            attrs = attributes_or_force
            route = Route(nlri, attrs)

        log.debug(lazymsg('rib.insert route={route}', route=route), 'rib')

        if not force and self.in_cache(route):
            return

        self._update_rib(route)

    def _update_rib(self, route: Route) -> None:
        # Validate: NLRIs entering RIB must have resolved nexthop
        # NextHopSelf/IPSelf should be resolved via neighbor.resolve_self() before reaching RIB
        nexthop = route.nlri.nexthop
        if getattr(nexthop, 'SELF', False) and not getattr(nexthop, 'resolved', True):
            raise RuntimeError(
                f'NLRI has unresolved NextHopSelf sentinel - call neighbor.resolve_self() before adding to RIB: {route.nlri}'
            )

        # route.nlri.index does not prepend the family
        route_index = route.index()
        route_family = route.nlri.family().afi_safi()
        route_attr_index = route.attributes.index()
        nlri_index = route.nlri.index()

        attr_af_nlri = self._new_attr_af_nlri
        new_nlri = self._new_nlri
        new_attr = self._new_attribute

        # Remove any pending withdraw for this NLRI (announce cancels previous withdraw)
        if route_family in self._pending_withdraws:
            self._pending_withdraws[route_family].pop(nlri_index, None)

        # add the route to the list to be announced/withdrawn
        attr_af_nlri.setdefault(route_attr_index, {}).setdefault(route_family, RIBdict({}))[route_index] = route
        new_nlri[route_index] = route
        new_attr[route_attr_index] = route.attributes
        self.update_cache(route)

    def updates(self, grouped: bool) -> Iterator[UpdateCollection | RouteRefresh]:
        if not self.enabled:
            return
        attr_af_nlri = self._new_attr_af_nlri
        new_attr = self._new_attribute

        # Get ready to accept more data
        self._new_nlri = {}
        self._new_attr_af_nlri = {}
        self._new_attribute = {}

        # Snapshot and clear pending withdraws
        pending_withdraws = self._pending_withdraws
        self._pending_withdraws = {}

        # Snapshot and clear refresh state to prevent race conditions
        # (resend() can be called during iteration and would modify these)
        refresh_families = self._refresh_families
        refresh_routes = self._refresh_routes
        self._refresh_families = set()
        self._refresh_routes = []

        # generating Updates from what is in the RIB
        # Changes in _new_attr_af_nlri may be announces OR withdraws (based on nlri.action)
        for attr_index, per_family in attr_af_nlri.items():
            for family, routes in per_family.items():
                if not routes:
                    continue

                attributes = new_attr[attr_index]

                # Validate and separate announces and withdraws based on nlri.action
                for route in routes.values():
                    if route.nlri.action == Action.UNSET:
                        raise RuntimeError(f'NLRI action is UNSET (not set to ANNOUNCE or WITHDRAW): {route.nlri}')
                announces = [route.nlri for route in routes.values() if route.nlri.action == Action.ANNOUNCE]
                withdraws = [route.nlri for route in routes.values() if route.nlri.action == Action.WITHDRAW]

                if family == (AFI.ipv4, SAFI.unicast) and grouped:
                    if announces:
                        yield UpdateCollection(announces, [], attributes)
                    if withdraws:
                        yield UpdateCollection([], withdraws, attributes)
                    continue

                if family == (AFI.ipv4, SAFI.mcast_vpn) and grouped:
                    if announces:
                        yield UpdateCollection(announces, [], attributes)
                    if withdraws:
                        yield UpdateCollection([], withdraws, attributes)
                    continue
                if family == (AFI.ipv6, SAFI.mcast_vpn) and grouped:
                    if announces:
                        yield UpdateCollection(announces, [], attributes)
                    if withdraws:
                        yield UpdateCollection([], withdraws, attributes)
                    continue

                # Non-grouped: one Update per NLRI
                for route in routes.values():
                    if route.nlri.action == Action.UNSET:
                        raise RuntimeError(f'NLRI action is UNSET (not set to ANNOUNCE or WITHDRAW): {route.nlri}')
                    if route.nlri.action == Action.WITHDRAW:
                        yield UpdateCollection([], [route.nlri], attributes)
                    else:
                        yield UpdateCollection([route.nlri], [], attributes)

        # Generate Updates for pending withdraws using the new Update signature
        # UpdateCollection(announces=[], withdraws=nlris, attributes) - no nlri.action needed
        # Yield one Update per NLRI to match original behavior
        for family, nlri_attr_dict in pending_withdraws.items():
            if not nlri_attr_dict:
                continue
            for nlri, attrs in nlri_attr_dict.values():
                # Use new 3-arg signature: (announces, withdraws, attributes)
                # Withdraws include attributes for proper BGP encoding (e.g., FlowSpec rate-limit)
                yield UpdateCollection([], [nlri], attrs)

        # Route Refresh - use snapshots to avoid modification during iteration

        for afi, safi in refresh_families:
            yield RouteRefresh.make_route_refresh(afi, safi, RouteRefresh.start)

        for route in refresh_routes:
            yield UpdateCollection([route.nlri], [], route.attributes)

        for afi, safi in refresh_families:
            yield RouteRefresh.make_route_refresh(afi, safi, RouteRefresh.end)
