"""word.py

The value types made of one word: most of the configuration.

`Word` reads one word and converts it; the conversion raises ValueError to refuse it, and
the type turns that into a positioned error. The reusable instances are declared once
here and named for what they read.

Copyright (c) 2009-2026 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from typing import Any, Callable, Generic, TypeVar, cast

from exabgp.configuration.grammar.error import ConfigError
from exabgp.configuration.grammar.shape import INT64_MAX, TEXT, Shape, boolean, enumeration, integer_ranges
from exabgp.configuration.grammar.types.base import Type, WordOrSyntax
from exabgp.configuration.grammar.words import Words

T = TypeVar('T')

# A number of the configuration is ASCII digits and nothing else. int() also reads a sign,
# `_` between digits and the digits of every script: `1_000`, `+5` and `٣` were numbers.
DECIMAL_DIGITS = frozenset('0123456789')
HEXADECIMAL_DIGITS = frozenset('0123456789abcdefABCDEF')


def is_decimal(word: str) -> bool:
    """Whether the word is a number written with the ASCII digits 0 to 9 alone."""
    return bool(word) and all(character in DECIMAL_DIGITS for character in word)


def decimal(word: str) -> int:
    """The number the word writes in ASCII digits; ValueError for any other word."""
    if not is_decimal(word):
        raise ValueError(f"'{word}' is not a number, it is written with the digits 0 to 9")
    return int(word)


def is_hexadecimal(word: str) -> bool:
    """Whether the word is 0x followed by ASCII hexadecimal digits alone."""
    return word[:2].lower() == '0x' and len(word) > 2 and all(character in HEXADECIMAL_DIGITS for character in word[2:])


def hexadecimal(word: str) -> int:
    """The number the word writes as 0x and ASCII hexadecimal digits; ValueError for any other word."""
    if not is_hexadecimal(word):
        raise ValueError(f"'{word}' is not a hexadecimal number, it is 0x and the digits 0 to 9, a to f")
    return int(word[2:], 16)


def lenient_number(word: str) -> bool:
    """Whether int() reads the word as a number which is not written in ASCII digits: `+5`, `1_0`."""
    if is_decimal(word):
        return False
    try:
        int(word)
    except ValueError:
        return False
    return True


def decimal_or_hexadecimal(word: str) -> int:
    """The number a word writes in ASCII decimal, or in hexadecimal after 0x."""
    return hexadecimal(word) if word[:2].lower() == '0x' else decimal(word)


class Word(Type[T], Generic[T]):
    def __init__(
        self,
        name: str,
        hint: str,
        convert: Callable[[str], T],
        examples: list[str],
        render: Callable[[T], list[str]] | None = None,
        choices: list[str] | None = None,
        shape: Shape = TEXT,
        doc: str = '',
    ) -> None:
        self.name = name
        self._hint = hint
        self._convert = convert
        self._examples = examples
        self._render = render or (lambda value: [str(value)])
        self._choices = choices or []
        self._shape = shape.described(doc)

    def parse(self, words: Words) -> T:
        where = words.where()
        word = words.word()
        try:
            return self._convert(word)
        except ValueError as exc:
            raise ConfigError(where, str(exc), expected=self._choices or [self._hint]) from None

    def render(self, value: T) -> list[WordOrSyntax]:
        return list(self._render(value))

    def hint(self) -> str:
        return self._hint

    def examples(self) -> list[str]:
        return list(self._examples)

    def choices(self, partial: str) -> list[str]:
        return [choice for choice in self._choices if choice.startswith(partial.lower())]

    def shape(self) -> Shape:
        return self._shape


Ranges = tuple[tuple[int, int], ...]


class Number(Word[T], Generic[T]):
    """A number within declared ranges, the constraint written once.

    The ranges give the check, the hint, the examples and the shape. `make` turns the number
    into the value kept (a MED attribute). A `convert` of its own, for the spellings the
    legacy parser took (`0x64`, `1.1`), must refuse what the ranges refuse: the tests check
    it at every bound.
    """

    def __init__(
        self,
        name: str,
        ranges: Ranges,
        make: Callable[[int], T] | None = None,
        convert: Callable[[str], T] | None = None,
        examples: list[str] | None = None,
        render: Callable[[T], list[str]] | None = None,
        hint: str = '',
        typedef: str = '',
        doc: str = '',
    ) -> None:
        self.ranges = ranges
        self._make = make
        bounds = [str(bound) for low, high in ranges for bound in dict.fromkeys((low, high))]
        super().__init__(
            name,
            hint or '|'.join(str(low) if low == high else f'<{low}-{high}>' for low, high in ranges),
            convert or self._number,
            examples if examples is not None else bounds,
            render=render,
            shape=_replace_typedef(integer_ranges(*ranges), typedef),
            doc=doc,
        )

    def _number(self, word: str) -> T:
        if not is_decimal(word):
            raise ValueError(f"'{word}' is not a valid {self.name}")
        number = int(word)
        if not any(low <= number <= high for low, high in self.ranges):
            raise ValueError(f'{self.name} {number} is invalid, it is {self._hint}')
        value: Any = number if self._make is None else self._make(number)
        return cast(T, value)


def _replace_typedef(shape: Shape, typedef: str) -> Shape:
    return Shape(shape.kind, ranges=shape.ranges, typedef=typedef) if typedef else shape


def spelled(
    name: str, true: tuple[str, ...], false: tuple[str, ...], bare: bool | None, lower: bool = True
) -> Word[bool]:
    """A boolean over the given spellings; `bare` is the value when no word is given."""

    def convert(word: str) -> bool:
        check = word.lower() if lower else word
        if check in true:
            return True
        if check in false:
            return False
        if not check and bare is not None:
            return bare
        raise ValueError(f"'{word}' is not a valid {name}")

    examples = [*true, *false] + ([''] if bare is not None else [])
    if lower:
        examples.append(true[0].upper())
    return Word(
        name,
        '|'.join((true[0], false[0])),
        convert,
        examples,
        render=lambda value: [true[0] if value else false[0]],
        choices=[*true, *false],
        shape=boolean(),
    )


def choice(name: str, choices: list[str], lower: bool = True) -> Word[str]:
    """One of a list of words, returned as written in the list."""

    def convert(word: str) -> str:
        check = word.lower() if lower else word
        for each in choices:
            if (each.lower() if lower else each) == check:
                return each
        raise ValueError(f"'{word}' is not a valid {name}")

    examples = list(choices) + ([choices[0].upper()] if lower else [])
    return Word(name, '|'.join(choices), convert, examples, choices=list(choices), shape=enumeration(*choices))


def integer(name: str, low: int | None = None, high: int | None = None) -> Number[int]:
    """A plain number; with no bounds any which is not negative: a number has no sign."""
    if low is None or high is None:
        return Number(name, ((0, INT64_MAX),), hint='<number>', examples=['0', '1'])
    return Number(name, ((low, high),))


def text(name: str, examples: list[str] | None = None) -> Word[str]:
    """Any one word, the empty word included."""
    return Word(name, f'<{name}>', str, examples if examples is not None else ['word', '"two words"', ''])
