"""basic.py

The value types which are not BGP: booleans, choices, free text, integers, programs.

Copyright (c) 2009-2026 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from enum import StrEnum
from typing import Generic, TypeVar

from exabgp.configuration.grammar.error import ConfigError
from exabgp.configuration.grammar.shape import TEXT, Shape, boolean, enumeration, leaf_list
from exabgp.configuration.grammar.types.base import Type
from exabgp.configuration.grammar.words import Words
from exabgp.util.program import resolve_program, validate_executable

E = TypeVar('E', bound=StrEnum)

TRUE_WORDS = ('true', 'enable', 'enabled', 'yes', '1')
FALSE_WORDS = ('false', 'disable', 'disabled', 'no', '0')


class Bool(Type[bool]):
    """A boolean, written in any of the usual ways, in any case.

    `bare` is the value of the keyword given with no word after it (`respawn;`). With no
    `bare`, a word is required.
    """

    name = 'boolean'

    def __init__(self, bare: bool | None = None) -> None:
        self.bare = bare

    def parse(self, words: Words) -> bool:
        where = words.where()
        word = words.word()
        lowered = word.lower()
        if lowered in TRUE_WORDS:
            return True
        if lowered in FALSE_WORDS:
            return False
        if not lowered and self.bare is not None:
            return self.bare
        raise ConfigError(where, f"'{word}' is not a valid boolean", expected=list(TRUE_WORDS + FALSE_WORDS))

    def render(self, value: bool) -> list[str]:
        return ['true' if value else 'false']

    def hint(self) -> str:
        return 'true|false'

    def examples(self) -> list[str]:
        spellings = [*TRUE_WORDS, *FALSE_WORDS, 'TRUE', 'Disable']
        if self.bare is not None:
            spellings.append('')
        return spellings

    def choices(self, partial: str) -> list[str]:
        return [word for word in ('true', 'false') if word.startswith(partial.lower())]

    def shape(self) -> Shape:
        return boolean()


class Choice(Type[E], Generic[E]):
    """One word out of a Python enumeration, in any case, returned as the enumeration member."""

    def __init__(self, enumeration: type[E], name: str = '') -> None:
        self.enumeration = enumeration
        self.name = name or 'choice'

    def _values(self) -> list[str]:
        return [member.value for member in self.enumeration]

    def parse(self, words: Words) -> E:
        where = words.where()
        word = words.word()
        for member in self.enumeration:
            if member.value == word.lower():
                return member
        raise ConfigError(where, f"'{word}' is not a valid {self.name}", expected=self._values())

    def render(self, value: E) -> list[str]:
        return [self.enumeration(value).value]

    def hint(self) -> str:
        return '|'.join(self._values())

    def examples(self) -> list[str]:
        return self._values() + [value.upper() for value in self._values()]

    def choices(self, partial: str) -> list[str]:
        return [value for value in self._values() if value.startswith(partial.lower())]

    def shape(self) -> Shape:
        return enumeration(*self._values())


class LegacyName(Type[str]):
    """The name of a section, as the legacy parser takes it: the word after the keyword.

    legacy: nothing is checked, and with no name the `{` itself is the name: `process {`
    is a process called `{`. Words after the name are ignored.
    """

    name = 'name'

    def parse(self, words: Words) -> str:
        return '{' if words.at_end() else words.word()

    def render(self, value: str) -> list[str]:
        return [value]

    def hint(self) -> str:
        return '<name>'

    def examples(self) -> list[str]:
        return ['name', 'with.dot-dash_underscore']


class Program(Type[list[str]]):
    """A program and its arguments: every word left in the statement.

    A relative path is looked for in /etc/exabgp, next to the configuration file and on the
    PATH. The program must exist and be something exabgp may run.
    """

    name = 'program'

    def parse(self, words: Words) -> list[str]:
        where = words.where()
        program = words.word()
        if not program:
            raise ConfigError(where, 'the "run" command requires a program path', expected=[self.hint()])
        if program[0] != '/':
            program = resolve_program(program, words.source)
        try:
            validate_executable(program)
        except ValueError as exc:
            raise ConfigError(where, str(exc)) from None
        return [program] + [token.word for token in words.rest()]

    def render(self, value: list[str]) -> list[str]:
        return list(value)

    def hint(self) -> str:
        return '<program> [<argument> ...]'

    def examples(self) -> list[str]:
        return ['/bin/cat', '/bin/cat --flag', '/bin/cat "with space"', 'cat']

    def shape(self) -> Shape:
        return leaf_list(TEXT, min_items=1)
