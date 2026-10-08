"""flow_validation.py

RFC 8955 section 6 (and RFC 8956 section 5): which received flow specifications are
feasible, judged against the unicast routes the same peer sent.

exabgp holds one adj-rib-in per neighbour and has no view across them, so "the best-match
unicast route" is the longest unicast prefix this peer announced which covers the flow's
destination. The check runs only when the neighbour asks for it (`flow-validation`), and
needs the adj-rib-in, which is where the unicast routes are read from.

Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import ipaddress
from typing import TYPE_CHECKING, cast

from exabgp.bgp.message.update.attribute import Attribute, AttributeCollection
from exabgp.bgp.message.update.attribute.aspath import SEQUENCE, ASPath
from exabgp.bgp.message.update.collection import RoutedNLRI, UpdateCollection
from exabgp.bgp.message.update.nlri.flow import Flow, Flow4Destination, Flow6Destination
from exabgp.bgp.message.update.nlri.inet import INET
from exabgp.logger import lazymsg, log
from exabgp.protocol.family import AFI, SAFI, FamilyTuple
from exabgp.rib import prefix_limit
from exabgp.rib.route import Route

if TYPE_CHECKING:
    from exabgp.bgp.neighbor import Neighbor
    from exabgp.rib.incoming import IncomingRIB

Network = ipaddress.IPv4Network | ipaddress.IPv6Network

# the flow family, and the unicast family its destination is validated against
VALIDATED: dict[FamilyTuple, FamilyTuple] = {
    (AFI.ipv4, SAFI.flow_ip): (AFI.ipv4, SAFI.unicast),
    (AFI.ipv6, SAFI.flow_ip): (AFI.ipv6, SAFI.unicast),
}

DISABLED = 'disable'
# rule a relaxed by explicit configuration: a flow with no destination is feasible
RELAXED = 'relaxed'

# the component type of a destination prefix, the same for IPv4 and IPv6
DESTINATION = Flow4Destination.ID


def _within(inner: Network, outer: Network) -> bool:
    """`inner` is `outer` or a prefix inside it, and false across address families."""
    if isinstance(inner, ipaddress.IPv4Network) and isinstance(outer, ipaddress.IPv4Network):
        return inner.subnet_of(outer)
    if isinstance(inner, ipaddress.IPv6Network) and isinstance(outer, ipaddress.IPv6Network):
        return inner.subnet_of(outer)
    return False


def _unicast_network(route: Route) -> Network:
    # the unicast families decode to INET
    return ipaddress.ip_network(cast(INET, route.nlri).cidr.prefix(), strict=False)


def _destination(flow: Flow) -> Network | None:
    """The destination prefix of rule a, or None when the flow has none it can use.

    RFC 8956 5: for IPv6 the component has to have an offset of 0. More than one
    destination is not a form the RFC writes, so it is not given a meaning here.
    """
    destinations = flow.rules.get(DESTINATION, [])
    if len(destinations) != 1:
        return None
    # the destination component of an IPv6 flow is a Flow6Destination, which has an offset
    if flow.afi == AFI.ipv6:
        destination6 = cast(Flow6Destination, destinations[0])
        if destination6.offset:
            return None
        return ipaddress.ip_network(destination6.cidr.prefix(), strict=False)
    return ipaddress.ip_network(cast(Flow4Destination, destinations[0]).cidr.prefix(), strict=False)


def _originator(attributes: AttributeCollection) -> str:
    """Who put the route into the AS: the ORIGINATOR_ID when a reflector passed it, else the peer."""
    return str(attributes.get(Attribute.CODE.ORIGINATOR_ID, ''))


def _neighbouring_as(attributes: AttributeCollection) -> int:
    """The AS the route came from, the leftmost of its AS_PATH, 0 for a route of our own AS."""
    if Attribute.CODE.AS_PATH not in attributes:
        return 0
    # the attribute stored under AS_PATH is the AS_PATH attribute
    segments = cast(ASPath, attributes[Attribute.CODE.AS_PATH]).aspath
    if segments and isinstance(segments[0], SEQUENCE) and segments[0]:
        return int(segments[0][0])
    return 0


def feasible(flow: Route, unicast: list[Route], mode: str) -> bool:
    """RFC 8955 6: rules a, b and c for one flow specification of one peer."""
    rules = cast(Flow, flow.nlri).rules
    destination = _destination(cast(Flow, flow.nlri))
    if destination is None:
        # rule a; relaxed, a flow with no destination passes and rules b and c are moot
        return mode == RELAXED and DESTINATION not in rules
    covering = [route for route in unicast if _within(destination, _unicast_network(route))]
    if not covering:
        return False
    best = max(covering, key=lambda route: _unicast_network(route).prefixlen)
    # rule b: the originator of the flow is the originator of the best-match unicast route
    if _originator(flow.attributes) != _originator(best.attributes):
        return False
    # rule c: no more-specific unicast route from another neighbouring AS
    neighbouring = _neighbouring_as(best.attributes)
    for route in unicast:
        network = _unicast_network(route)
        if network.prefixlen > destination.prefixlen and _within(network, destination):
            if _neighbouring_as(route.attributes) != neighbouring:
                return False
    return True


def _unicast_view(incoming: IncomingRIB, update: UpdateCollection) -> dict[FamilyTuple, list[Route]]:
    """The unicast routes of the peer once this UPDATE is applied: the RIB, plus and minus it."""
    view: dict[FamilyTuple, dict[bytes, Route]] = {}
    for family in VALIDATED.values():
        view[family] = {route.index(): route for route in incoming.cached_routes([family])}
    for nlri in update.withdraws:
        family = nlri.family().afi_safi()
        if family in view:
            view[family].pop(Route(nlri, AttributeCollection()).index(), None)
    for routed in update.announces:
        family = routed.nlri.family().afi_safi()
        if family in view:
            route = Route(routed.nlri, update.attributes, routed.nexthop)
            view[family][route.index()] = route
    return {family: list(routes.values()) for family, routes in view.items()}


def _withhold(neighbor: Neighbor, route: Route) -> list[UpdateCollection]:
    """Hold back a received flow which is not feasible, returning the withdrawal of the one it replaces.

    RFC 4271 9: a route sent again replaces the one the adj-rib-in holds. Not feasible, the
    new one is held back, so the older one leaves service rather than staying in it beside
    the replacement, and the API is told it is withdrawn.
    """
    incoming = neighbor.rib.incoming
    replaced: list[UpdateCollection] = []
    older = incoming.cached_route(route.nlri)
    if older is not None:
        incoming.update_cache_withdraw(older.nlri)
        prefix_limit.release(neighbor, older.nlri)
        replaced.append(UpdateCollection([], [older.nlri], older.attributes))
    held = incoming.hold_pending_flow(route)
    log.info(
        lazymsg(
            'flow.validation.withheld peer={peer} flow="{flow}" held={held} replaced={replaced}',
            peer=neighbor.session.peer_address,
            flow=route.nlri,
            held=held,
            replaced=older is not None,
        ),
        'routes',
    )
    assert incoming.cached_route(route.nlri) is None, 'a flow held back is not in the adj-rib-in'
    return replaced


def _judge_received(
    neighbor: Neighbor, update: UpdateCollection, view: dict[FamilyTuple, list[Route]]
) -> list[UpdateCollection]:
    """Withhold the flow specifications of this UPDATE which are not feasible.

    Returns the withdrawals of the flows they replaced, for the API to be told.
    """
    incoming = neighbor.rib.incoming
    # RFC 4271 9: the withdrawn routes first. The prefix-limit stops counting them now, so a
    # flow this UPDATE makes feasible is counted against what the peer holds once it applies
    for nlri in update.withdraws:
        if nlri.family().afi_safi() in VALIDATED:
            incoming.discard_pending_flow(nlri)
            prefix_limit.release(neighbor, nlri)
    withheld: list[RoutedNLRI] = []
    replaced: list[UpdateCollection] = []
    for routed in update.announces:
        family = routed.nlri.family().afi_safi()
        if family not in VALIDATED:
            continue
        route = Route(routed.nlri, update.attributes, routed.nexthop)
        if feasible(route, view[VALIDATED[family]], neighbor.flow_validation):
            incoming.discard_pending_flow(routed.nlri)
            continue
        withheld.append(routed)
        replaced.extend(_withhold(neighbor, route))
    if withheld:
        update.withhold(withheld)
    return replaced


def _revalidate(neighbor: Neighbor, view: dict[FamilyTuple, list[Route]]) -> list[UpdateCollection]:
    """RFC 8955 6: the unicast routes changed, so every flow is judged again."""
    incoming = neighbor.rib.incoming
    changes: list[UpdateCollection] = []
    for family, unicast_family in VALIDATED.items():
        unicast = view[unicast_family]
        for route in list(incoming.cached_routes([family])):
            if feasible(route, unicast, neighbor.flow_validation):
                continue
            incoming.update_cache_withdraw(route.nlri)
            prefix_limit.release(neighbor, route.nlri)
            # RFC 4271 9: a flow held back is newer than the one in the adj-rib-in, it was
            # sent to replace it, so it is never overwritten by the older one
            incoming.hold_pending_flow(route, replace=False)
            changes.append(UpdateCollection([], [route.nlri], route.attributes))
        for route in incoming.pending_flows(family):
            if not feasible(route, unicast, neighbor.flow_validation):
                continue
            # RFC 4486 4: it enters the adj-rib-in, so it counts as one the UPDATE handler installs
            prefix_limit.admit(neighbor, route.nlri)
            incoming.discard_pending_flow(route.nlri)
            incoming.update_cache(route)
            changes.append(UpdateCollection([RoutedNLRI(route.nlri, route.nexthop)], [], route.attributes))
    return changes


def validate_flows(neighbor: Neighbor, update: UpdateCollection) -> list[UpdateCollection]:
    """Apply RFC 8955 6 to a received UPDATE, before the API or the adj-rib-in see it.

    The infeasible flow specifications of the UPDATE are taken out of it and held. When
    the UPDATE changes the peer's unicast routes, the flows already held are judged again:
    what that changes is applied to the adj-rib-in and returned, for the API to be told.
    """
    if neighbor.flow_validation == DISABLED:
        return []
    view = _unicast_view(neighbor.rib.incoming, update)
    replaced = _judge_received(neighbor, update, view)
    unicast = set(VALIDATED.values())
    if not any(nlri.family().afi_safi() in unicast for nlri in update.nlris):
        return replaced
    return replaced + _revalidate(neighbor, view)
