"""compare.py

Read a configuration with the legacy parser and with the grammar, and compare the results.

This exists while both parsers do (plan/wip-config-grammar.md): it backs
`exabgp configuration validate --parser both` and the differential tests, and goes when
the legacy parser goes.

Two parsers agree when both accept with equal results, or both refuse; the error messages
may differ.

Copyright (c) 2009-2026 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from typing import Any, Callable

from exabgp.bgp.neighbor import Neighbor

from exabgp.configuration.configuration import Configuration
from exabgp.configuration.grammar.engine import NotMigrated
from exabgp.configuration.grammar.read import read_file, read_text
from exabgp.configuration.settings import ConfigurationSettings

LEGACY = 'legacy'
GRAMMAR = 'grammar'
BOTH = 'both'
PARSERS = (LEGACY, GRAMMAR, BOTH)


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
    state['asm'] = {family: str(message) for family, message in neighbor.asm.items()}
    state['messages'] = [str(message) for message in neighbor.messages]
    state['rib'] = (neighbor.rib.name, neighbor.rib.enabled)
    return state


def outcome(configuration: Configuration) -> Accepted:
    """What a configuration produced, reduced to what the two parsers must agree on."""
    return Accepted(
        processes=dict(configuration.processes),
        neighbors={name: neighbor_state(neighbor) for name, neighbor in configuration.neighbors.items()},
    )


def _read(configuration: Configuration, parser: str) -> tuple[Outcome, Configuration]:
    if not configuration.reload(parser):
        return Rejected(str(configuration.error)), configuration
    return outcome(configuration), configuration


def legacy_text(text: str) -> tuple[Outcome, Configuration]:
    return _read(Configuration([text], text=True), LEGACY)


def legacy_file(path: str) -> tuple[Outcome, Configuration]:
    return _read(Configuration([path]), LEGACY)


def _declared(read: Callable[[str], ConfigurationSettings], source: str) -> bool:
    """Whether the grammar reads the configuration; NotMigrated when it uses an undeclared section.

    A refusal for any other reason is reported by the reload which follows, with its message.
    """
    try:
        read(source)
    except NotMigrated:
        raise
    except (ValueError, OSError):
        return False
    return True


def grammar_text(text: str) -> tuple[Outcome, Configuration]:
    _declared(read_text, text)
    return _read(Configuration([text], text=True), GRAMMAR)


def grammar_file(path: str) -> tuple[Outcome, Configuration]:
    _declared(read_file, path)
    return _read(Configuration([path]), GRAMMAR)


def agree(first: Outcome, second: Outcome) -> bool:
    if isinstance(first, Rejected) and isinstance(second, Rejected):
        return True
    return first == second


def difference(legacy: Outcome, grammar: Outcome) -> str:
    """A description of how the two outcomes differ, empty when they agree."""
    if agree(legacy, grammar):
        return ''
    if isinstance(legacy, Rejected):
        return f'only the grammar accepts it, the legacy parser says:\n{legacy.message}'
    if isinstance(grammar, Rejected):
        return f'only the legacy parser accepts it, the grammar says:\n{grammar.message}'
    return '\n'.join(
        _differences('', legacy.processes, grammar.processes) + _differences('', legacy.neighbors, grammar.neighbors)
    )


# a difference report names at most this many places, the first ones are what matter
MAX_DIFFERENCES = 20


def _differences(path: str, old: Any, new: Any) -> list[str]:
    """Where two nested values differ, as `path: legacy != grammar` lines."""
    found: list[str] = []
    stack = [(path, old, new)]
    while stack and len(found) < MAX_DIFFERENCES:
        where, left, right = stack.pop()
        if isinstance(left, dict) and isinstance(right, dict):
            for key in sorted(set(left) | set(right), key=str, reverse=True):
                stack.append((f'{where}/{key}', left.get(key, '<absent>'), right.get(key, '<absent>')))
        elif left != right:
            found.append(f'{where or "/"}\n  legacy:  {left!r}\n  grammar: {right!r}')
    return found
