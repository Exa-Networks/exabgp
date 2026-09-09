"""store.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Iterator

from exabgp.bgp.message import UpdateCollection
from exabgp.bgp.message.refresh import RouteRefresh
from exabgp.bgp.message.update.collection import RoutedNLRI
from exabgp.protocol.ip import IP
from exabgp.logger import lazymsg, log
from exabgp.protocol.family import AFI, SAFI, FamilyTuple
from exabgp.rib.cache import Cache

if TYPE_CHECKING:
    from exabgp.bgp.message.update.attribute.collection import AttributeCollection
    from exabgp.bgp.message.update.nlri.nlri import NLRI
    from exabgp.rib.route import Route

# This is needs to be an ordered dict
RIBdict = dict


class _PathSelection:
    """What one prefix has sent to a peer which limits its paths, and what it is holding.

    `advertised` is an index and not a route: enforcement only counts, and the routes
    themselves live in the adj-rib-out cache when the operator asked for one. `candidates`
    holds the withheld paths, and only those, because a withheld path is the one thing this
    class knows which is written down nowhere else: it is what a later withdraw promotes.
    """

    def __init__(self) -> None:
        self.candidates: dict[bytes, Route] = {}
        self.advertised: set[bytes] = set()

    def empty(self) -> bool:
        return not self.candidates and not self.advertised


class OutgoingRIB(Cache):
    _watchdog: dict[str, dict[str, dict[bytes, Route]]]
    _new_nlri: dict[bytes, Route]
    _new_attr_af_nlri: dict[bytes, dict[FamilyTuple, dict[bytes, Route]]]
    _new_attribute: dict[bytes, AttributeCollection]
    _refresh_families: set[FamilyTuple]
    _refresh_routes: list[Route]

    # New structure for withdraws - avoids deepcopy by not modifying nlri.action
    # Indexed by family -> nlri_index -> (NLRI, AttributeCollection)
    _pending_withdraws: dict[FamilyTuple, dict[bytes, tuple['NLRI', 'AttributeCollection']]]

    def __init__(self, cache: bool, families: set[FamilyTuple], enabled: bool = True) -> None:
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
        self._path_selection: dict[FamilyTuple, dict[bytes, _PathSelection]] = {}
        self._session_epoch = 0

        # Flush callbacks for sync mode - fire when updates() exhausts
        self._flush_callbacks: list[asyncio.Event] = []

        self.reset()

    # will resend all the routes once we reconnect
    def reset(self) -> None:
        # WARNING : this function can run while we are in the updates() loop too !
        #
        # It used to drain that loop to clear the queues, which it can no longer do: a
        # drained batch admits paths against the peer's limit, and the peer this batch was
        # for has gone. Clearing the queues here does the same job, and the epoch is how
        # the loop still running finds out it is generating for a session which has ended.
        self._session_epoch += 1
        self._refresh_families = set()
        self._refresh_routes = []
        self._new_nlri = {}
        self._new_attr_af_nlri = {}
        self._new_attribute = {}
        self._pending_withdraws = {}
        self._path_selection = {}

    # back to square one, all the routes are removed
    def clear(self) -> None:
        self.clear_cache()
        self.reset()

    def delete_cached_family(self, families: set[FamilyTuple]) -> None:
        super().delete_cached_family(families)
        for family in list(self._path_selection):
            if family not in families:
                del self._path_selection[family]

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

    def resend(self, enhanced_refresh: bool, family: FamilyTuple | None = None) -> None:
        if not self.enabled:
            return
        requested_families = set(self.families)

        if family is not None:
            requested_families = set(self.families).intersection([family])

        if enhanced_refresh:
            for family in requested_families:
                self._refresh_families.add(family)

        # What a refresh replays is the adj-rib-out, and nothing else. A limited family used
        # to replay its held paths from _path_selection when there was no cache, which made
        # "adj-rib-out false" mean one thing for a family with a limit and another for a
        # family without one, in the same neighbour.
        for route in self.cached_routes(list(requested_families)):
            self._refresh_routes.append(route)

    def withdraw(self, families: set[FamilyTuple] | None = None) -> None:
        if not self.enabled:
            return
        if not families:
            families = self.families
        requested_families = set(families).intersection(self.families)

        # Same reasoning as resend(): what can be withdrawn is what the adj-rib-out holds.
        for route in self.cached_routes(list(requested_families)):
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
                old_index = route.index()
                # add_to_rib handles announces - no need to set action on route
                self.add_to_rib(route)
                self._watchdog[watchdog].setdefault('+', {})[route.index()] = route
                self._watchdog[watchdog]['-'].pop(old_index)

    def withdraw_watchdog(self, watchdog: str) -> None:
        if not self.enabled:
            return
        if watchdog in self._watchdog:
            for route in list(self._watchdog[watchdog].get('+', {}).values()):
                self.del_from_rib(route)
                self._watchdog[watchdog].setdefault('-', {})[route.index()] = route
                self._watchdog[watchdog]['+'].pop(route.index())

    def del_from_rib(self, route: 'Route') -> None:
        """Remove a route from the RIB.

        Args:
            route: The Route to remove
        """
        if not self.enabled:
            return

        nlri = route.nlri
        attrs = route.attributes
        route_index = route.index()
        self._del_from_rib_impl(nlri, attrs, route_index)

    def del_nlri_from_rib(self, nlri: 'NLRI', attributes: 'AttributeCollection | None' = None) -> None:
        """Remove an NLRI from the RIB.

        Args:
            nlri: The NLRI to remove
            attributes: Optional attributes (unused, kept for API compatibility)
        """
        if not self.enabled:
            return

        route_index = self._make_index(nlri)
        self._del_from_rib_impl(nlri, attributes, route_index)

    def _del_from_rib_impl(self, nlri: 'NLRI', attrs: 'AttributeCollection | None', route_index: bytes) -> None:
        """Shared implementation for route removal."""

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

    def add_to_rib(self, route: 'Route', force: bool = False) -> None:
        """Add a route to the RIB.

        Args:
            route: The Route to add (must have resolved nexthop)
            force: If True, add even if already in cache
        """
        if not self.enabled:
            return

        log.debug(lazymsg('rib.insert route={route}', route=route), 'rib')

        if not force and self.in_cache(route):
            return

        self._update_rib(route)

    def add_nlri_to_rib(self, nlri: 'NLRI', attributes: 'AttributeCollection', force: bool = False) -> None:
        """Add an NLRI with attributes to the RIB.

        Convenience method that creates a Route and delegates to add_to_rib.

        Args:
            nlri: The NLRI to add
            attributes: The attributes for the route
            force: If True, add even if already in cache
        """
        from exabgp.rib.route import Route

        route = Route(nlri, attributes, nexthop=IP.NoNextHop)
        self.add_to_rib(route, force)

    def _update_rib(self, route: Route) -> None:
        # Validate: Routes entering RIB must have resolved nexthop
        # NextHopSelf/IPSelf should be resolved via neighbor.resolve_self() before reaching RIB
        nexthop = route.nexthop
        if getattr(nexthop, 'SELF', False) and not getattr(nexthop, 'resolved', True):
            raise RuntimeError(
                f'Route has unresolved NextHopSelf sentinel - call neighbor.resolve_self() before adding to RIB: {route.nlri}'
            )

        # route.nlri.index does not prepend the family
        route_index = route.index()
        route_family = route.nlri.family().afi_safi()
        route_attr_index = route.attributes.index()

        attr_af_nlri = self._new_attr_af_nlri
        new_nlri = self._new_nlri
        new_attr = self._new_attribute

        # Note: Cancel logic removed - announce does NOT cancel pending withdraw
        # This allows withdraw+announce sequences to both be sent
        # See plan/plan-announce-cancels-withdraw-optimization.md for future optimization

        # add the route to the list to be announced
        attr_af_nlri.setdefault(route_attr_index, {}).setdefault(route_family, RIBdict({}))[route_index] = route
        new_nlri[route_index] = route
        new_attr[route_attr_index] = route.attributes
        self.update_cache(route)

    def updates(
        self,
        grouped: bool,
        paths_limit: dict[FamilyTuple, int] | None = None,
    ) -> Iterator[UpdateCollection | RouteRefresh]:
        if not self.enabled:
            return
        epoch = self._session_epoch
        for update in self._generate_updates(grouped, paths_limit or {}):
            yield update
            # A disconnect can reset the RIB while the consumer is sending.
            if epoch != self._session_epoch:
                return

    def _admit_path(self, route: Route, limit: int, refresh: bool = False) -> bool:
        if not limit:
            return True
        family = route.nlri.family().afi_safi()
        prefixes = self._path_selection.get(family)
        if prefixes is None:
            prefixes = self._path_selection[family] = {}
        prefix = route.nlri.prefix_index()
        selection = prefixes.get(prefix)
        if selection is None:
            selection = prefixes[prefix] = _PathSelection()
        index = route.index()
        if index in selection.advertised:
            return True
        if len(selection.advertised) >= limit:
            # A refresh replays what the peer already has, so it must not overwrite a path
            # held since before it with the same one arriving again.
            if refresh:
                selection.candidates.setdefault(index, route)
            else:
                selection.candidates[index] = route
            # A route the operator configured is not reaching the peer. It is held, not
            # dropped, and show adj-rib out still lists it, so without this line there is
            # nothing anywhere to tell them the peer never received it.
            log.debug(
                lazymsg(
                    'rib.paths_limit.withheld family={family} prefix={prefix} limit={limit}',
                    family=family,
                    prefix=route.nlri,
                    limit=limit,
                ),
                'rib',
            )
            return False
        # It is going out, so it is no longer something to promote later.
        selection.candidates.pop(index, None)
        selection.advertised.add(index)
        assert len(selection.advertised) <= limit
        assert not (selection.advertised & selection.candidates.keys()), 'a path is sent or held, never both'
        return True

    def _withdraw_path(self, nlri: NLRI) -> bool:
        family = nlri.family().afi_safi()
        prefixes = self._path_selection.get(family)
        if prefixes is None:
            return True
        prefix = nlri.prefix_index()
        selection = prefixes.get(prefix)
        if selection is None:
            return False
        index = self._make_index(nlri)
        selection.candidates.pop(index, None)
        advertised = index in selection.advertised
        selection.advertised.discard(index)
        if selection.empty():
            del prefixes[prefix]
        return advertised

    def _promote_paths(
        self, changed: dict[tuple[FamilyTuple, bytes], None], paths_limit: dict[FamilyTuple, int], grouped: bool
    ) -> Iterator[UpdateCollection]:
        # A promoted path is an announce like any other, so it batches like one.
        promoted: dict[tuple[bytes, FamilyTuple], list[Route]] = {}
        for family, prefix in changed:
            selection = self._path_selection.get(family, {}).get(prefix)
            if selection is None:
                continue
            limit = paths_limit.get(family, 0)
            # Held paths only, in the order they were offered, since ExaBGP has no view of
            # which path is better. list() because a promoted one leaves the collection.
            for index, route in list(selection.candidates.items()):
                if limit and len(selection.advertised) >= limit:
                    break
                del selection.candidates[index]
                selection.advertised.add(index)
                # The counterpart of rib.paths_limit.withheld: the slot freed by a withdraw
                # is what lets this one through, and both halves belong in the log.
                log.debug(
                    lazymsg(
                        'rib.paths_limit.promoted family={family} prefix={prefix} limit={limit}',
                        family=family,
                        prefix=route.nlri,
                        limit=limit,
                    ),
                    'rib',
                )
                promoted.setdefault((route.attributes.index(), family), []).append(route)

        for (_, family), routes in promoted.items():
            yield from self._announce_updates(routes, routes[0].attributes, family, grouped)

    def _generate_updates(
        self, grouped: bool, paths_limit: dict[FamilyTuple, int]
    ) -> Iterator[UpdateCollection | RouteRefresh]:
        # Everything this batch will send is taken and replaced in one go, because the RIB
        # keeps accepting while we generate: add_to_rib, del_from_rib and resend() all run
        # from the reactor between two of our yields, and would otherwise change the
        # collections we are walking.
        attr_af_nlri = self._new_attr_af_nlri
        new_attr = self._new_attribute
        latest_routes = self._new_nlri
        self._new_nlri = {}
        self._new_attr_af_nlri = {}
        self._new_attribute = {}
        pending_withdraws = self._pending_withdraws
        self._pending_withdraws = {}
        refresh_families = self._refresh_families
        refresh_routes = self._refresh_routes
        self._refresh_families = set()
        self._refresh_routes = []

        # Route refresh goes first: the flush which asked for it comes, to the operator,
        # before anything they announced afterwards in the same reactor cycle.
        for afi, safi in refresh_families:
            yield RouteRefresh.make_route_refresh(afi, safi, RouteRefresh.start)
        for route in refresh_routes:
            limit = paths_limit.get(route.nlri.family().afi_safi(), 0)
            if self._admit_path(route, limit, refresh=True):
                yield UpdateCollection([RoutedNLRI(route.nlri, route.nexthop)], [], route.attributes)
        for afi, safi in refresh_families:
            yield RouteRefresh.make_route_refresh(afi, safi, RouteRefresh.end)

        # Withdraws go before announces, which preserves the order the operator asked for
        # and is what lets a withdrawal free a slot an announce in this same batch can use.
        # A dict rather than a set: which prefixes get backfilled is decided here, and the
        # order they are offered in should be the order they were withdrawn, not the order
        # their hashes happen to fall in.
        changed: dict[tuple[FamilyTuple, bytes], None] = {}
        for family, withdrawals in pending_withdraws.items():
            for nlri, attributes in withdrawals.values():
                if family in self._path_selection:
                    changed[(family, nlri.prefix_index())] = None
                if self._withdraw_path(nlri):
                    yield UpdateCollection([], [nlri], attributes)

        for attr_index, per_family in attr_af_nlri.items():
            for family, routes in per_family.items():
                limit = paths_limit.get(family, 0)
                # The same NLRI queued twice leaves an entry under each attribute set, and
                # del_from_rib only unhooks the one filed under the attributes _new_nlri
                # points at. The other entry outlived the withdraw and was announced after
                # it, leaving the peer holding a route we had just withdrawn.
                #
                # An NLRI still in _new_nlri has not been withdrawn, whichever attributes
                # it now carries, so announcing every queued attribute set for it stands:
                # that is a redefinition, and both go out as they always have.
                # The gate reads one structure to decide the fate of another, so say what
                # has to hold between them: an announce leaves _new_nlri only by being
                # withdrawn, never by being dropped.
                assert all(
                    index in latest_routes or route.nlri.index() in pending_withdraws.get(family, {})
                    for index, route in routes.items()
                ), 'a queued announce left _new_nlri without a withdraw'
                selected = [
                    route
                    for index, route in routes.items()
                    if index in latest_routes and self._admit_path(route, limit)
                ]
                if selected:
                    yield from self._announce_updates(selected, new_attr[attr_index], family, grouped)
        # Only prefixes touched by withdrawals need candidate promotion.
        yield from self._promote_paths(changed, paths_limit, grouped)

    @staticmethod
    def _announce_updates(
        routes: list[Route], attributes: AttributeCollection, family: FamilyTuple, grouped: bool
    ) -> Iterator[UpdateCollection]:
        if grouped and family in ((AFI.ipv4, SAFI.unicast), (AFI.ipv4, SAFI.mcast_vpn), (AFI.ipv6, SAFI.mcast_vpn)):
            announces = [RoutedNLRI(route.nlri, route.nexthop) for route in routes]
            yield UpdateCollection(announces, [], attributes)
            return
        for route in routes:
            yield UpdateCollection([RoutedNLRI(route.nlri, route.nexthop)], [], attributes)
