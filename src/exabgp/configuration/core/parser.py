"""tokeniser.py

Created by Thomas Mangin on 2015-06-05.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from collections import deque
from typing import TYPE_CHECKING, Generator, Iterable, Iterator

if TYPE_CHECKING:
    from exabgp.configuration.core.error import Error
    from exabgp.configuration.core.scope import Scope

from exabgp.configuration.core.format import tokens
from exabgp.protocol.family import AFI

# Minimum line length for parameters extraction
MIN_LINE_LENGTH_FOR_PARAMS = 2  # Minimum line tokens needed to have parameters


class Tokeniser:
    def __init__(self) -> None:
        self.next: deque[str] = deque()
        self.tokens: list[str] = []
        self.generator: Iterator[str] = iter([])
        self.announce: bool = True
        self.afi = AFI.undefined
        self.fname: str = ''
        self.consumed: int = 0

    def replenish(self, content: list[str]) -> 'Tokeniser':
        self.next.clear()
        self.tokens = content
        self.generator = iter(content)
        self.consumed = 0
        return self

    def clear(self) -> None:
        self.replenish([])
        self.announce = True

    def peek(self) -> str:
        """Peek at next token without incrementing consumed counter."""
        if self.next:
            return self.next[0]

        try:
            peaked = next(self.generator)
            self.next.append(peaked)
            return peaked
        except StopIteration:
            return ''

    def _get(self) -> str:
        """Get next token, incrementing consumed counter."""
        if self.next:
            self.consumed += 1
            return self.next.popleft()

        try:
            tok = next(self.generator)
            self.consumed += 1
            return tok
        except StopIteration:
            return ''

    def __call__(self) -> str:
        return self._get()

    def consume(self, name: str) -> None:
        next_tok = self._get()
        if next_tok != name:
            raise ValueError(f"expected '{name}' but found '{next_tok}' instead")

    def consume_if_match(self, name: str) -> bool:
        next_tok = self.peek()
        if next_tok == name:
            self._get()
            return True
        return False

    def remaining_string(self) -> str:
        """Get remaining tokens as the original command substring.

        Uses tokeniser.consumed to know how many words were consumed
        during dispatch, then extracts the remaining portion of
        the original command string.

        Args:
            tokeniser: Tokeniser with consumed count
            original: Original command string

        Returns:
            Remaining portion of original command after consumed words
        """

        return ' '.join([_ for _ in self.next] + [_ for _ in self.generator])


class Parser:
    @staticmethod
    def _off() -> Iterator[list[str]]:
        return iter([])

    def __init__(self, scope: Scope, error: Error) -> None:
        self.scope: Scope = scope
        self.error: Error = error
        self.finished = False
        self.number = 0
        self.line: list[str] = []
        self.tokeniser: Tokeniser = Tokeniser()
        self.end = ''
        self.index_column = 0
        self.index_line = 0
        self.fname = ''
        self.type = 'unset'

        self._tokens: Iterator[list[str]] = Parser._off()
        self._next: list[str] = []
        self._data: Generator[list[str], None, None] | None = None

    def clear(self) -> None:
        self.finished = False
        self.number = 0
        self.line = []
        self.tokeniser.clear()
        self.end = ''
        self.index_column = 0
        self.index_line = 0
        self.fname = ''
        self.type = 'unset'
        if self._data:
            self._set(self._data)

    def params(self) -> str:
        if len(self.line) <= MIN_LINE_LENGTH_FOR_PARAMS:
            return ''
        if self.end in ('{', '}', ';'):
            joined = "' '".join(self.line[1:-1])
            return f"'{joined}'"
        joined = "' '".join(self.line[1:])
        return f"'{joined}'"

    def _tokenise(self, iterator: Iterable[str]) -> Generator[list[str], None, None]:
        for parsed in tokens(iterator):
            words = [word for y, x, word in parsed]
            self.line = words  # Store the word list, not a joined string
            # ignore # lines
            # set Location information
            yield words

    def _set(self, function: Generator[list[str], None, None]) -> bool | str:
        try:
            self._tokens = function
            self._next = next(self._tokens)
        except OSError as exc:
            error = str(exc)
            if error.count(']'):
                self.error.set(error.split(']')[1].strip())
            else:
                self.error.set(error)
            self._tokens = Parser._off()
            self._next = []
            return self.error.set('issue setting the configuration parser')
        except StopIteration:
            self._tokens = Parser._off()
            self._next = []
            return self.error.set('issue setting the configuration parser, no data')
        return True

    def set_file(self, data: str) -> bool | str:
        def _source(fname: str) -> Generator[list[str], None, None]:
            with open(fname, 'r') as fileobject:

                def formated() -> Generator[str, None, None]:
                    line = ''
                    for current in fileobject:
                        self.index_line += 1
                        current = current.rstrip()
                        if current.endswith('\\'):
                            line += current
                            continue
                        if line:
                            yield line + current
                            line = ''
                            continue
                        yield current
                    if line:
                        yield line + current

                for _ in self._tokenise(formated()):
                    yield _

        self.type = 'file'
        self.fname = data
        self.tokeniser.fname = data
        return self._set(_source(data))

    def set_text(self, data: str) -> bool | str:
        def _source(data: str) -> Generator[list[str], None, None]:
            for _ in self._tokenise(data.split('\n')):
                yield _

        self.type = 'text'
        return self._set(_source(data))

    def set_api(self, line: str) -> bool | str:
        return self._set(self._tokenise(iter([line])))

    def set_action(self, command: str) -> None:
        if command != 'announce':
            self.tokeniser.announce = False

    def __call__(self) -> list[str]:
        self.number += 1
        try:
            self.line, self._next = self._next, next(self._tokens)
            self.end = self.line[-1]
        except StopIteration:
            if not self.finished:
                self.finished = True
                self.line, self._next = self._next, []
                self.end = self.line[-1]
            else:
                self.line = []
                self.end = ''

        # should we raise a Location if called with no more data ?
        self.tokeniser.replenish(self.line[:-1])

        return self.line
