"""context.py

What one read, or one print, of a configuration keeps across its statements.

The values of a block are its own: what a statement tells a statement of another block goes
through the context. A route line leaves its address family for the next-hop after it, a
route leaves itself for the neighbor which closes next, a template for the neighbors which
inherit it.

Copyright (c) 2009-2026 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import count
from typing import TYPE_CHECKING, Any, Iterator

from exabgp.protocol.family import AFI

if TYPE_CHECKING:
    from exabgp.configuration.grammar.lexer import Token
    from exabgp.rib.route import Route


@dataclass
class ReadContext:
    # the words of the statement being read, keyword included
    statement: tuple[Token, ...] = ()
    # the address family of the prefix a route line starts with: what `next-hop self` means
    afi: AFI = AFI.undefined
    # the address family of the MUP route being read, for its next-hop
    mup_afi: AFI | None = None
    # an API command announces its routes, or withdraws them
    announce: bool = True
    # the routes read and not yet taken by a neighbor or a template
    routes: list[Route] = field(default_factory=list)
    # the values of each template by name, for the neighbors which inherit it
    templates: dict[str, dict[str, Any]] = field(default_factory=dict)
    # the index of each neighbor made, a second with the same one is refused
    neighbor_indexes: list[bytes] = field(default_factory=list)
    # legacy: api names are unique across the whole configuration, not per neighbor
    api_names: set[str] = field(default_factory=set)
    # the statements of the Collector block being read, in their order: (what, value).
    # One list is enough: no collector block is ever inside another
    pending: list[tuple[Any, Any]] = field(default_factory=list)

    def take_routes(self) -> list[Route]:
        """The routes not yet taken, now taken: those read after them start a new list."""
        routes, self.routes = self.routes, []
        return routes


@dataclass
class PrintContext:
    # an api block is named when printed, counting through the whole configuration: one
    # left unnamed is named for the microsecond it is read in, and two could share it
    api_names: Iterator[int] = field(default_factory=lambda: count(1))
