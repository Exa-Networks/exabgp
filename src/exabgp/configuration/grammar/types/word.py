"""word.py

The value types made of one word: most of the configuration.

`Word` reads one word and converts it; the conversion raises ValueError to refuse it, and
the type turns that into a positioned error. The reusable instances are declared once
here and named for what they read.

Copyright (c) 2009-2026 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from typing import Any, Callable, Generic, TypeVar

from exabgp.configuration.grammar.error import ConfigError
from exabgp.configuration.grammar.types.base import Type
from exabgp.configuration.grammar.words import Words

T = TypeVar('T')


class Word(Type[T], Generic[T]):
    def __init__(
        self,
        name: str,
        hint: str,
        convert: Callable[[str], T],
        examples: list[str],
        render: Callable[[T], list[str]] | None = None,
        choices: list[str] | None = None,
        schema: dict[str, Any] | None = None,
    ) -> None:
        self.name = name
        self._hint = hint
        self._convert = convert
        self._examples = examples
        self._render = render or (lambda value: [str(value)])
        self._choices = choices or []
        self._schema = schema or {'type': 'string'}

    def parse(self, words: Words) -> T:
        where = words.where()
        word = words.word()
        try:
            return self._convert(word)
        except ValueError as exc:
            raise ConfigError(where, str(exc), expected=self._choices or [self._hint]) from None

    def render(self, value: T) -> list[str]:
        return self._render(value)

    def hint(self) -> str:
        return self._hint

    def examples(self) -> list[str]:
        return list(self._examples)

    def choices(self, partial: str) -> list[str]:
        return [choice for choice in self._choices if choice.startswith(partial.lower())]

    def json_schema(self) -> dict[str, Any]:
        return dict(self._schema)


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
        schema={'type': 'boolean'},
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
    return Word(name, '|'.join(choices), convert, examples, choices=list(choices), schema={'enum': list(choices)})


def integer(name: str, low: int | None = None, high: int | None = None) -> Word[int]:
    def convert(word: str) -> int:
        try:
            number = int(word)
        except ValueError:
            raise ValueError(f"'{word}' is not a valid {name}") from None
        if low is not None and number < low:
            raise ValueError(f'{name} {number} is below {low}')
        if high is not None and number > high:
            raise ValueError(f'{name} {number} is above {high}')
        return number

    examples = [str(low if low is not None else 0), str(high if high is not None else 1)]
    schema: dict[str, Any] = {'type': 'integer'}
    if low is not None:
        schema['minimum'] = low
    if high is not None:
        schema['maximum'] = high
    return Word(name, '<number>' if low is None else f'<{low}-{high}>', convert, examples, schema=schema)


def text(name: str, examples: list[str] | None = None) -> Word[str]:
    """Any one word, the empty word included."""
    return Word(name, f'<{name}>', str, examples if examples is not None else ['word', '"two words"', ''])
