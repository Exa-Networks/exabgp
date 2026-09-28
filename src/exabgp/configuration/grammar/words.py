"""words.py

The words of one statement, as a type reads them.

Copyright (c) 2009-2026 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from typing import Any

from exabgp.configuration.grammar.lexer import Token


class Words:
    """The words after the keyword of a statement, consumed from the front.

    Reading past the end gives an empty word positioned on the terminator, which is what
    the legacy tokeniser gives, and lets every type report "missing value" at the place
    the value should have been.
    """

    def __init__(self, tokens: tuple[Token, ...], end: Token, context: dict[str, Any] | None = None) -> None:
        self._tokens = tokens
        self._end = end
        self._index = 0
        # what the values of one statement tell each other: the address family of the prefix
        # a route line starts with decides what `next-hop self` means
        self.context: dict[str, Any] = context if context is not None else {}

    @property
    def source(self) -> str:
        return self._end.source

    def at_end(self) -> bool:
        return self._index >= len(self._tokens)

    def peek(self) -> str:
        return '' if self.at_end() else self._tokens[self._index].word

    def token(self) -> Token:
        """The next token, without consuming it."""
        if self.at_end():
            return Token('', self._end.source, self._end.line, self._end.column)
        return self._tokens[self._index]

    def where(self) -> str:
        return self.token().where()

    def take(self) -> Token:
        token = self.token()
        if not self.at_end():
            self._index += 1
        assert self._index <= len(self._tokens)
        return token

    def word(self) -> str:
        return self.take().word

    def rest(self) -> list[Token]:
        """Everything left, consumed."""
        left = list(self._tokens[self._index :])
        self._index = len(self._tokens)
        return left

    def left(self) -> int:
        return len(self._tokens) - self._index
