"""section.py

The code a tree of nodes runs, beside the value types (types/base.py):

    Section  what a block stands for: built from its values when it closes, taken apart
             again to be printed
    Store    where the value of a statement goes, when it is not simply set or added to a list

A Collector is a Section whose statements are used together, in the order they were given,
when it closes: its leaves keep their value with a Pending store.

A neighbor is read the legacy way, its values merged with those of its templates first, so
its parts are made by a Codec each, which also gives the statements of its part back:

    Codec    one part of a neighbor, from its statements into NeighborSettings, and back

Each is a base class: every section and every store of the configuration is a subclass,
found with `Section.__subclasses__()` or by any editor.

Copyright (c) 2009-2026 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import dataclasses
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, ClassVar, Generic, TypeVar

from exabgp.configuration.grammar.context import PrintContext, ReadContext

if TYPE_CHECKING:
    from exabgp.bgp.neighbor.settings import NeighborSettings

T = TypeVar('T')

# the values of a block by field, as its statements give them
Values = dict[str, Any]


def fields(built: Any) -> Values:
    """The values by field of a Settings object, the inverse of what a block builds."""
    if isinstance(built, dict):
        return built
    if dataclasses.is_dataclass(built) and not isinstance(built, type):
        return {each.name: getattr(built, each.name) for each in dataclasses.fields(built)}
    raise TypeError(f'can not render {type(built).__name__}, it is not a dataclass')


class Section(ABC, Generic[T]):
    """What a block stands for. A section keeps no state: what a read shares is in the context."""

    def opened(self, context: ReadContext) -> None:
        """Called when the block opens, before any of its statements."""

    def finish(self, values: Values) -> None:
        """Checks and rewrites once every statement of the block is read, raises ValueError."""

    @abstractmethod
    def build(self, name: Any, values: Values, context: ReadContext) -> T:
        """What the block stands for, made from its name and its values; raises ValueError."""

    def unbuild(self, name: Any, built: Any, context: PrintContext) -> tuple[Any, Values]:
        """For printing: the name and the values by field which build `built` again.

        `built` is what build() made or, for a block kept EXTEND, one entry of the list it made.
        """
        return name, fields(built)


class Kept(Section[Values]):
    """The values as they are, for the block around it to use."""

    def build(self, name: Any, values: Values, context: ReadContext) -> Values:
        return values


KEPT = Kept()


class Store(ABC):
    """Where the value of a statement goes. A store keeps no state either."""

    @abstractmethod
    def keep(self, values: Values, value: Any, context: ReadContext) -> None:
        """Keep `value` in the values of its block, or in the context; raises ValueError."""


class Pending(Store):
    """The value of a statement of a Collector block, kept in order with `what` says how to use it."""

    def __init__(self, what: Any = None) -> None:
        self.what = what

    def keep(self, values: Values, value: Any, context: ReadContext) -> None:
        context.pending.append((self.what, value))


class Collector(Section[T]):
    """A block whose statements are used together, in their order, when it closes."""

    def opened(self, context: ReadContext) -> None:
        # the entries of a block closed with an error are not those of the next one
        context.pending = []

    def build(self, name: Any, values: Values, context: ReadContext) -> T:
        entries, context.pending = context.pending, []
        return self.collected(name, values, entries, context)

    @abstractmethod
    def collected(self, name: Any, values: Values, entries: list[tuple[Any, Any]], context: ReadContext) -> T:
        """What the block stands for, from the (what, value) of its statements in their order."""


class Codec(ABC):
    """One part of a neighbor: set from the values of the neighbor block, and printed back.

    The codecs of a neighbor run in their order, each on the NeighborSettings the ones before
    it filled: the add-path families are those of the families part.
    """

    # the fields of the neighbor block this part is made from, and printed as
    fields: ClassVar[tuple[str, ...]] = ()

    @abstractmethod
    def resolve(self, values: Values, settings: NeighborSettings) -> None:
        """Set this part of `settings` from the values of the neighbor; raises ValueError."""

    @abstractmethod
    def unresolve(self, settings: NeighborSettings, context: PrintContext) -> Values:
        """The values, by field, which resolve to this part of `settings`: None where nothing is said."""
