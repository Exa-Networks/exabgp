"""nodes.py

The shapes a configuration statement takes.

    Leaf     keyword value ;
    Block    keyword [name] { ... }

A block builds what it stands for from the values of its statements, with its Section
(section.py): a Settings object, or for the sections read the legacy way (neighbor and
what is inside it) the values themselves, merged and resolved by the block around them.

A block names the Settings it builds and the leaves name the fields they fill, so the
tree read by the engine, printed by the renderer and described by the help is one and the
same declaration.

Copyright (c) 2009-2026 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field as dataclass_field
from enum import Enum
from typing import Any

from exabgp.configuration.grammar.context import ReadContext
from exabgp.configuration.grammar.section import KEPT, Section, Store
from exabgp.configuration.grammar.types.base import Type


class _Missing:
    """No default: the field is left out when the configuration does not set it."""

    # one object, compared with `is`: a copy of a leaf default (describe.py deepcopies them)
    # must still be MISSING. A compiled class can not return a cached object from __new__,
    # so the copies give back the object itself
    def __copy__(self) -> '_Missing':
        return self

    def __deepcopy__(self, memo: dict[int, Any]) -> '_Missing':
        return self

    def __repr__(self) -> str:
        return 'MISSING'


MISSING: Any = _Missing()


class Collect(Enum):
    """How a leaf given more than once is kept."""

    SET = 'set'  # the last one wins
    APPEND = 'append'  # a list, one entry per statement
    EXTEND = 'extend'  # a list, the entries of every statement one after the other


class Keep(Enum):
    """How a block is kept by the block around it."""

    SINGLE = 'single'  # one; opening it again continues the same values
    NAMED = 'named'  # a dict by name, a name used twice is refused
    LIST = 'list'  # a list, one entry per block
    EXTEND = 'extend'  # a list, the entries each block builds added one after the other


@dataclass(frozen=True)
class Leaf:
    keyword: str
    type: Type[Any]
    field: str
    default: Any = MISSING
    mandatory: bool = False  # the block is refused without it, when it closes
    doc: str = ''
    collect: Collect = Collect.SET
    store: Store | None = None
    # the statement may be given several times, each adding an entry (a route, a family):
    # what a data model makes a list. A store callback alone says nothing about it
    multiple: bool = False
    # given by the neighbor or by a template it inherits: checked once they are merged, when
    # the neighbor is made (tree/resolve.py), so a template may leave it out
    needed: bool = False
    # given again, the statement adds to what was given (communities, flow rules) where its
    # value is not a list in the model: the help says "may be repeated" of it, as of a list
    adds: bool = False

    @property
    def repeated(self) -> bool:
        """Whether the printer writes one statement per entry of the value."""
        return self.store is not None or self.collect == Collect.APPEND

    @property
    def many(self) -> bool:
        """Whether the value is a list of entries, in the data model."""
        return self.multiple or self.collect != Collect.SET

    def keep(self, values: dict[str, Any], value: Any, context: ReadContext) -> None:
        if self.store is not None:
            self.store.keep(values, value, context)
        elif self.collect == Collect.APPEND:
            values.setdefault(self.field, []).append(value)
        elif self.collect == Collect.EXTEND:
            values.setdefault(self.field, []).extend(value)
        else:
            values[self.field] = value


@dataclass(frozen=True)
class Block:
    keyword: str
    field: str
    section: Section[Any] = KEPT
    children: tuple['Leaf | Block', ...] = ()
    keep: Keep = Keep.SINGLE
    # the type of the word(s) naming the block (`process <name> {`, `neighbor <ip> {`)
    name: Type[Any] | None = None
    # in the data model, the member holding that name: the key of the list of such blocks
    key: str = 'name'
    # the block is complete once read (a neighbor, not a template): its needed leaves are there
    complete: bool = False
    doc: str = ''
    # the message when a mandatory leaf is missing, per section, as the legacy parser words it
    missing: str = 'missing {names}'
    # a statement and a section may share a keyword: `route <prefix> ...;` and `route <prefix> { }`
    _leaves: dict[str, Leaf] = dataclass_field(default_factory=dict, init=False, repr=False, compare=False)
    _blocks: dict[str, 'Block'] = dataclass_field(default_factory=dict, init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        for child in self.children:
            index: dict[str, Any] = self._leaves if isinstance(child, Leaf) else self._blocks
            assert child.keyword not in index, f'{child.keyword} declared twice in {self.keyword}'
            index[child.keyword] = child

    def leaf(self, keyword: str) -> Leaf | None:
        return self._leaves.get(keyword)

    def block(self, keyword: str) -> 'Block | None':
        return self._blocks.get(keyword)

    def leaves(self) -> list[Leaf]:
        return [child for child in self.children if isinstance(child, Leaf)]

    def blocks(self) -> list['Block']:
        return [child for child in self.children if isinstance(child, Block)]
