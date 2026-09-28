"""lists.py

One value, or several in brackets: `community 1:1;` and `community [ 1:1 2:2 ];`.

The list is a type wrapping the type of its items, so the syntax help, the examples and
the printer come from the item: nothing about brackets is written inside a value parser.

The legacy lists differ in the details, each reproduced by an option: whether a comma
separates items or is read as one (and refused by it), whether `[ ]` is allowed, whether
an item given twice is kept.

Copyright (c) 2009-2026 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from enum import Enum
from typing import Generic, TypeVar

from exabgp.configuration.grammar.error import ConfigError
from exabgp.configuration.grammar.shape import Shape, leaf_list
from exabgp.configuration.grammar.types.base import Syntax, Type
from exabgp.configuration.grammar.words import Words

T = TypeVar('T')

OPEN = '['
CLOSE = ']'
COMMA = ','
# a list is written by hand, a real one holds a handful of items
MAX_ITEMS = 1024


class Commas(Enum):
    SKIP = 'skip'  # `[ a, b ]` is `[ a b ]`
    ITEM = 'item'  # a comma is given to the item type, which refuses it


class OneOrList(Type[list[T]], Generic[T]):
    def __init__(
        self,
        item: Type[T],
        name: str = '',
        commas: Commas = Commas.SKIP,
        empty: bool = True,
        unique: bool = False,
        single: bool = True,
        max_items: int = MAX_ITEMS,
    ) -> None:
        self.item = item
        self.name = name or f'{item.name} list'
        self.commas = commas
        self.empty = empty
        self.unique = unique  # an item given twice is kept once
        self.single = single  # one item may be given without brackets
        self.max_items = max_items

    def parse(self, words: Words) -> list[T]:
        where = words.where()
        if words.peek() != OPEN:
            if not self.single:
                raise ConfigError(where, f'invalid {self.name}', expected=[self.hint()])
            return [self.item.parse(words)]
        words.take()
        found: list[T] = []
        for _ in range(self.max_items + 1):
            if words.at_end():
                raise ConfigError(words.where(), f"invalid {self.name}, missing closing '{CLOSE}'")
            if words.peek() == CLOSE:
                words.take()
                if not found and not self.empty:
                    raise ConfigError(where, f'{self.name} is empty')
                return found
            if words.peek() == COMMA and self.commas == Commas.SKIP:
                words.take()
                continue
            value = self.item.parse(words)
            if not (self.unique and value in found):
                found.append(value)
        raise ConfigError(where, f'a {self.name} holds at most {self.max_items} items')

    def render(self, value: list[T]) -> list[str]:
        if len(value) == 1 and self.single:
            return self.item.render(value[0])
        rendered: list[str] = [Syntax(OPEN)]
        for each in value:
            rendered.extend(self.item.render(each))
        rendered.append(Syntax(CLOSE))
        return rendered

    def hint(self) -> str:
        item = self.item.hint()
        listed = f'{OPEN} {item} ... {CLOSE}'
        return f'{item}|{listed}' if self.single else listed

    def examples(self) -> list[str]:
        items = [example for example in self.item.examples() if example][:2] or ['']
        examples = [f'{OPEN} {items[0]} {CLOSE}', f'{OPEN} {" ".join(items)} {CLOSE}']
        if self.single:
            examples.insert(0, items[0])
        if self.commas == Commas.SKIP and len(items) > 1:
            examples.append(f'{OPEN} {", ".join(items)} {CLOSE}')
        if self.empty:
            examples.append(f'{OPEN} {CLOSE}')
        return examples

    def choices(self, partial: str) -> list[str]:
        return self.item.choices(partial)

    def shape(self) -> Shape:
        # one item without brackets is a way of writing a list of one, not another value
        return leaf_list(self.item.shape(), min_items=0 if self.empty else 1, max_items=self.max_items)
