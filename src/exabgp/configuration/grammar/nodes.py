"""nodes.py

The shapes a configuration statement takes.

    Leaf     keyword value ;
    Block    keyword [name] { ... }

A block builds what it stands for from the values of its statements: a Settings object,
or for the sections read the legacy way (neighbor and what is inside it) the values
themselves, merged and resolved by the block around them.

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
from typing import Any, Callable

from exabgp.configuration.grammar.types.base import Type


class _Missing:
    """No default: the field is left out when the configuration does not set it."""

    _instance: '_Missing | None' = None

    def __new__(cls) -> '_Missing':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

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


# (values, value, context of the read) -> None, for a leaf whose value is not simply set or
# added to a list
Store = Callable[[dict[str, Any], Any, dict[str, Any]], None]


@dataclass(frozen=True)
class Leaf:
    keyword: str
    type: Type[Any]
    field: str
    default: Any = MISSING
    mandatory: bool = False
    doc: str = ''
    collect: Collect = Collect.SET
    store: Store | None = None

    @property
    def repeated(self) -> bool:
        """Whether the printer writes one statement per entry of the value."""
        return self.store is not None or self.collect == Collect.APPEND

    def keep(self, values: dict[str, Any], value: Any, context: dict[str, Any]) -> None:
        if self.store is not None:
            self.store(values, value, context)
        elif self.collect == Collect.APPEND:
            values.setdefault(self.field, []).append(value)
        elif self.collect == Collect.EXTEND:
            values.setdefault(self.field, []).extend(value)
        else:
            values[self.field] = value


# (name, values by field, context of the whole read) -> what the block stands for
Builder = Callable[[Any, dict[str, Any], dict[str, Any]], Any]


def raw(name: Any, values: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    """The builder of a block whose values are used as they are, by the block around it."""
    return values


@dataclass(frozen=True)
class Block:
    keyword: str
    field: str
    build: Builder = raw
    children: tuple['Leaf | Block', ...] = ()
    keep: Keep = Keep.SINGLE
    # the type of the word(s) naming the block (`process <name> {`, `neighbor <ip> {`)
    name: Type[Any] | None = None
    doc: str = ''
    # the message when a mandatory leaf is missing, per section, as the legacy parser words it
    missing: str = 'missing {names}'
    # checks and rewrites once every statement of the block is read, raises ValueError
    finish: Callable[[dict[str, Any]], None] | None = None
    # called with the read context when the block opens, before any of its statements
    opened: Callable[[dict[str, Any]], None] | None = None
    # for printing: (what was built, context of the whole print) -> (name, values by field,
    # as the statements give them)
    unbuild: Callable[[Any, dict[str, Any]], tuple[Any, dict[str, Any]]] | None = None
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
