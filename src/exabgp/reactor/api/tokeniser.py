"""tokeniser.py

The words of an API command: how a command line is split, and read word by word.

Moved from the legacy configuration parser (configuration/core), which the API shared: the
configuration is now read by the grammar (configuration/grammar), the API commands still by
these.

Created by Thomas Mangin on 2015-06-05.
Copyright (c) 2009-2026 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from collections import deque
from typing import Iterator

from exabgp.protocol.family import AFI


def formated(line: str) -> str:
    changed_line = '#'
    new_line = (
        line.strip()
        .replace('\t', ' ')
        .replace(']', ' ]')
        .replace('[', '[ ')
        .replace(')', ' )')
        .replace('(', '( ')
        .replace(',', ' , ')
    )
    while new_line != changed_line:
        changed_line = new_line
        new_line = new_line.replace('  ', ' ')
    return new_line


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
