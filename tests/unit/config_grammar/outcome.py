"""outcome.py

What a configuration makes, reduced to what can be compared and frozen: the processes, and
for each neighbor what the configuration decided about it (routes included).

It compared the legacy parser with the grammar while both existed; it now backs the frozen
results (frozen.py) and the tests reading a configuration.

Copyright (c) 2009-2026 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from typing import Any

from exabgp.bgp.neighbor import Neighbor

from exabgp.configuration.configuration import Configuration


@dataclass(frozen=True)
class Accepted:
    processes: dict[str, Any]
    neighbors: dict[str, dict[str, Any]]


@dataclass(frozen=True)
class Rejected:
    message: str


Outcome = Accepted | Rejected


# what a Neighbor holds which is not configuration: identity, counters, live state
_NEIGHBOR_RUNTIME = frozenset({'uid', 'rib', 'counter', 'previous', 'eor', 'refresh', 'messages', 'asm', 'routes'})


def _dataclass_state(value: Any) -> dict[str, Any]:
    return {each.name: getattr(value, each.name) for each in dataclasses.fields(value)}


def route_state(route: Any) -> tuple[Any, ...]:
    """A route as the parsers must agree on it: the NLRI class and index, the text, every attribute."""
    attributes = tuple(
        (code, type(attribute).__name__, str(attribute)) for code, attribute in sorted(route.attributes.items())
    )
    return (type(route.nlri).__name__, *_nlri(route), repr(route.nexthop), attributes)


def _nlri(route: Any) -> tuple[str, str]:
    """The NLRI index and the route text, or why there are none.

    Both parsers build an IPv4 route from an IPv6 prefix given in an IPv4 family, whose NLRI
    can not be decoded to be shown.
    """
    from exabgp.bgp.message.notification import Notify

    try:
        return str(route.nlri.index().hex()), repr(route)
    except Notify as exc:
        return f'broken NLRI: {exc}', f'broken NLRI: {exc}'


def neighbor_state(neighbor: Neighbor) -> dict[str, Any]:
    """Everything the configuration decided about a neighbor.

    Neighbor.__eq__ is not used: it compares what forces a session reset on reload, and
    leaves out what can change without one.
    """
    state = {key: value for key, value in vars(neighbor).items() if key not in _NEIGHBOR_RUNTIME}
    state['session'] = _dataclass_state(neighbor.session)
    state['capability'] = _dataclass_state(neighbor.capability)
    state['routes'] = [route_state(route) for route in neighbor.routes]
    state['asm'] = {family: _operational_state(message) for family, message in neighbor.asm.items()}
    state['messages'] = [_operational_state(message) for message in neighbor.messages]
    state['rib'] = (neighbor.rib.name, neighbor.rib.enabled)
    return state


def _operational_state(message: Any) -> tuple[str, Any, Any]:
    """The text of an operational message leaves out its sequence and router-id."""
    return str(message), getattr(message, 'sequence', None), getattr(message, 'routerid', None)


def outcome(configuration: Configuration) -> Accepted:
    """What a configuration produced, reduced to what the two parsers must agree on."""
    return Accepted(
        processes=dict(configuration.processes),
        neighbors={name: neighbor_state(neighbor) for name, neighbor in configuration.neighbors.items()},
    )


def _read(configuration: Configuration) -> tuple[Outcome, Configuration]:
    if not configuration.reload():
        return Rejected(str(configuration.error)), configuration
    return outcome(configuration), configuration


def read_text(text: str) -> tuple[Outcome, Configuration]:
    return _read(Configuration([text], text=True))


def read_file(path: str) -> tuple[Outcome, Configuration]:
    return _read(Configuration([path]))


def agree(first: Outcome, second: Outcome) -> bool:
    if isinstance(first, Rejected) and isinstance(second, Rejected):
        return True
    return first == second
