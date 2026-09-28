"""install.py

Make the neighbors a configuration read with the grammar describes, as the legacy parser
made them at the end of a neighbor section (ParseNeighbor._post_finalize).

Copyright (c) 2009-2026 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from copy import deepcopy

from exabgp.bgp.message.operational import OperationalFamily
from exabgp.bgp.neighbor import Neighbor
from exabgp.bgp.neighbor.settings import NeighborSettings
from exabgp.protocol.family import FamilyTuple
from exabgp.protocol.ip import IPRange


def _init(neighbor: Neighbor, operational: list[OperationalFamily], neighbors: dict[str, Neighbor]) -> None:
    families = neighbor.families()
    for route in neighbor.routes:
        route = neighbor.resolve_self(route)
        if route.nlri.family().afi_safi() in families:
            neighbor.rib.outgoing.add_to_rib_watchdog(route)
    for message in operational:
        family = message.family()
        if family not in families:
            continue
        if message.NAME == 'ASM':
            neighbor.asm[family] = message
        else:
            neighbor.messages.append(message)
    neighbors[neighbor.name()] = neighbor


def session_of(neighbor: Neighbor, family: FamilyTuple) -> Neighbor:
    """One session of a multi-session neighbor: the neighbor with this family alone.

    draft-ietf-idr-bgp-multisession-07 groups sessions by their MULTIPROTOCOL capability, one
    family each (trivial groups), so the session advertises its family and no other: its
    name, its RIB, its ADD-PATH and next-hop families all follow from it.
    """
    session = deepcopy(neighbor)
    for other in neighbor.families():
        if other != family:
            session.remove_family(other)
    for other in neighbor.addpaths():
        if other != family:
            session.remove_addpath(other)
    for afi, safi, nexthop_afi in neighbor.nexthops():
        if (afi, safi) != family:
            session.remove_nexthop(afi, safi, nexthop_afi)
    session.make_rib()
    return session


def install(neighbor_settings: list[NeighborSettings]) -> dict[str, Neighbor]:
    """The neighbors by name; one per family for a multi-session neighbor."""
    neighbors: dict[str, Neighbor] = {}
    for each in neighbor_settings:
        neighbor = Neighbor.from_settings(each, rib=False)
        neighbor.routes = [neighbor.resolve_self(route) for route in neighbor.routes]
        # the peer-address of a configured neighbor is always a range, read by IP_RANGE
        assert isinstance(neighbor.session.peer_address, IPRange)
        neighbor.range_size = neighbor.session.peer_address.mask.size()
        if neighbor.capability.multi_session.is_enabled() and len(neighbor.families()) > 1:
            for family in neighbor.families():
                _init(session_of(neighbor, family), each.operational, neighbors)
            continue
        neighbor.make_rib()
        _init(neighbor, each.operational, neighbors)
    return neighbors
