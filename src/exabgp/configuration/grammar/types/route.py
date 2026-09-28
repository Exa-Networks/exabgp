"""route.py

What every statement reading routes does: `route 10.0.0.0/24 next-hop 1.2.3.4 med 10;`,
`flow ...;`, `vpls ...;`, an announce family line, an API command.

A route statement reads `<keyword> <value>` pairs from a table of the values it takes, each
applied as it is read, and prints each route it made back as the words it reads.

Copyright (c) 2009-2026 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from abc import abstractmethod
from enum import Enum
from typing import Any, Iterator, Mapping

from exabgp.configuration.grammar.error import ConfigError
from exabgp.configuration.grammar.types.base import Type
from exabgp.configuration.grammar.words import Words
from exabgp.rib.route import Route

MAX_ROUTE_VALUES = 256  # the keyword and value pairs of one route, far past a real one


class Target(Enum):
    """What the value of a route statement sets."""

    NLRI = 'nlri'  # a field of the NLRI settings, named by the value
    NEXTHOP = 'nexthop'  # the next-hop, an address
    NEXTHOP_ATTRIBUTE = 'nexthop-attribute'  # the next-hop and the attribute given with it
    ATTRIBUTE = 'attribute'  # an attribute of the route
    RULE = 'rule'  # the rules of a flow match, added to its NLRI
    NOTHING = 'nothing'  # read and not kept: `accept`


class RouteStatement(Type[list[Route]]):
    # the error for a keyword the table does not have, as each statement of the legacy parser worded it
    unknown = "Unknown command '{keyword}'"
    # the error for a route of more than MAX_ROUTE_VALUES values; None, legacy: the rest is not read
    too_many: str | None = 'a route holds at most {count} values'

    def keywords(self, words: Words, table: Mapping[str, Any], stop: str = '') -> Iterator[tuple[str, Any]]:
        """Where each keyword is and what the table has for it, until the words end or `stop`.

        The caller reads the value, `spec.type.parse(words)`, before asking for the next one.
        """
        for _ in range(MAX_ROUTE_VALUES):
            where = words.where()
            keyword = words.word()
            if not keyword or keyword == stop:
                return
            spec = table.get(keyword)
            if spec is None:
                raise ConfigError(where, self.unknown.format(keyword=keyword), expected=sorted(table))
            yield where, spec
        if self.too_many is not None:
            raise ConfigError(words.where(), self.too_many.format(count=MAX_ROUTE_VALUES))

    @abstractmethod
    def printed(self, route: Route) -> list[str]:
        """The words which read back as `route`."""

    def render(self, value: list[Route]) -> list[str]:
        return [word for route in value for word in self.printed(route)]
