"""install.py

Make the neighbors a configuration read with the grammar describes, as the legacy parser
made them at the end of a neighbor section (ParseNeighbor._post_finalize).

Copyright (c) 2009-2026 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from copy import deepcopy

from exabgp.bgp.neighbor import Neighbor
from exabgp.bgp.neighbor.settings import NeighborSettings
from exabgp.protocol.ip import IPRange


def _init(neighbor: Neighbor, neighbors: dict[str, Neighbor]) -> None:
    families = neighbor.families()
    for route in neighbor.routes:
        route = neighbor.resolve_self(route)
        if route.nlri.family().afi_safi() in families:
            neighbor.rib.outgoing.add_to_rib_watchdog(route)
    neighbors[neighbor.name()] = neighbor


def install(settings: list[NeighborSettings]) -> dict[str, Neighbor]:
    """The neighbors by name; one per family for a multi-session neighbor."""
    neighbors: dict[str, Neighbor] = {}
    for each in settings:
        neighbor = Neighbor.from_settings(each, rib=False)
        neighbor.routes = [neighbor.resolve_self(route) for route in neighbor.routes]
        # the peer-address of a configured neighbor is always a range, read by IP_RANGE
        assert isinstance(neighbor.session.peer_address, IPRange)
        neighbor.range_size = neighbor.session.peer_address.mask.size()
        if neighbor.capability.multi_session.is_enabled() and len(neighbor.families()) > 1:
            for family in neighbor.families():
                session = deepcopy(neighbor)
                session.make_rib()
                session.rib.outgoing.families = {family}
                _init(session, neighbors)
            continue
        neighbor.make_rib()
        _init(neighbor, neighbors)
    return neighbors
