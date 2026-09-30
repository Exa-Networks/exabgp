"""base.py

What every value type of the configuration can do.

A type reads its value from the words of a statement, prints a value back as words the
same type reads, says in a few characters what it expects, lists every spelling it
accepts, and completes a partial word.

Copyright (c) 2009-2026 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from exabgp.configuration.grammar.error import ConfigError
from exabgp.configuration.grammar.shape import TEXT, Shape
from exabgp.configuration.grammar.words import Words

T = TypeVar('T')


class Syntax:
    """A structural word (`[`, `]`, `(`, ...), printed as is and never quoted.

    It holds the word rather than being a str: mypyc cannot compile a subclass of str. It
    is equal to, and hashed like, the str it holds, so a rendered list compares with words.
    """

    __slots__ = ('word',)

    def __init__(self, word: str) -> None:
        self.word = word

    def __str__(self) -> str:
        return self.word

    def __repr__(self) -> str:
        return repr(self.word)

    def __hash__(self) -> int:
        return hash(self.word)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Syntax):
            return self.word == other.word
        if isinstance(other, str):
            return self.word == other
        return NotImplemented

    def __ne__(self, other: object) -> bool:
        return not self == other


# what a type renders a value as: the words, some of them structure
WordOrSyntax = str | Syntax


def spoken(words: list[WordOrSyntax]) -> str:
    """Rendered words as one line of text, for help and examples, where nothing is quoted."""
    return ' '.join(str(word) for word in words)


class Printed:
    """A value given to the printer as its words already, where the route holds the text of it.

    It holds the words rather than being a list: mypyc cannot compile a subclass of list.
    """

    __slots__ = ('words',)

    def __init__(self, words: list[WordOrSyntax]) -> None:
        self.words = words


class Type(ABC, Generic[T]):
    name = 'value'  # how an error refers to what was expected

    @abstractmethod
    def parse(self, words: Words) -> T:
        """Read a value, raising ConfigError positioned on the word at fault."""

    @abstractmethod
    def render(self, value: T) -> list[WordOrSyntax]:
        """The words which parse back to `value`."""

    @abstractmethod
    def hint(self) -> str:
        """What the syntax help shows for this value: `<asn>`, `text|json`."""

    @abstractmethod
    def examples(self) -> list[str]:
        """Every accepted spelling, as configuration text, for the forms tests."""

    def choices(self, partial: str) -> list[str]:
        """Completions of `partial`, for the types with a closed set of words."""
        return []

    def shape(self) -> Shape:
        """What the value is once read (grammar/shape.py): the data model, for JSON Schema and YANG."""
        return TEXT

    def fail(self, words: Words, message: str, expected: list[str] | None = None) -> ConfigError:
        return ConfigError(words.where(), message, expected=expected if expected is not None else [self.hint()])
