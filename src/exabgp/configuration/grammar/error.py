"""error.py

The one error the grammar raises.

It is a ValueError, as every configuration error in exabgp is, and it knows where it
happened, what was expected there and what the operator may have meant.

Copyright (c) 2009-2026 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import re
from typing import Any

MAX_EXPECTED_SHOWN = 24  # beyond this the list stops helping and the hint says enough
MAX_SUGGESTIONS = 3
MAX_SUGGESTION_DISTANCE = 2
MAX_SUGGESTION_LENGTH = 64  # a longer word is not a typo of a keyword, and costs length squared to compare

# what Token.where() writes: `<source>:<line>:<column>`, or `line <line>:<column>` with no source
WHERE = re.compile(r'^(?:line |(?P<source>.+):)(?P<line>[0-9]+):(?P<column>[0-9]+)$')


class ConfigError(ValueError):
    def __init__(
        self,
        where: str,
        message: str,
        expected: list[str] | None = None,
        suggestions: list[str] | None = None,
    ) -> None:
        self.where = where
        self.message = message
        self.expected = list(expected or [])
        self.suggestions = list(suggestions or [])
        ValueError.__init__(self, self.render())

    def render(self) -> str:
        lines = [f'{self.where}: {self.message}' if self.where else self.message]
        if self.suggestions:
            lines.append(f'  did you mean: {", ".join(self.suggestions)}')
        if self.expected:
            shown = self.expected[:MAX_EXPECTED_SHOWN]
            more = ', ...' if len(self.expected) > MAX_EXPECTED_SHOWN else ''
            lines.append(f'  expected: {", ".join(shown)}{more}')
        return '\n'.join(lines)

    def as_dict(self) -> dict[str, Any]:
        """The error for a program to read: the position split, every expected word."""
        found = WHERE.match(self.where)
        return {
            'file': found['source'] if found else None,
            'line': int(found['line']) if found else None,
            'column': int(found['column']) if found else None,
            'message': self.message,
            'expected': list(self.expected),
            'suggestions': list(self.suggestions),
        }


def distance(first: str, second: str) -> int:
    """Levenshtein distance, the number of single character edits between two words."""
    if len(first) < len(second):
        first, second = second, first
    previous = list(range(len(second) + 1))
    for row, left in enumerate(first, start=1):
        current = [row]
        for column, right in enumerate(second, start=1):
            current.append(min(previous[column] + 1, current[column - 1] + 1, previous[column - 1] + (left != right)))
        previous = current
    return previous[-1]


def suggest(word: str, candidates: list[str]) -> list[str]:
    """The candidates close enough to `word` to be what was meant, closest first."""
    if len(word) > MAX_SUGGESTION_LENGTH:
        return []
    lowered = word.lower()
    scored = sorted((distance(lowered, candidate.lower()), candidate) for candidate in candidates)
    return [candidate for score, candidate in scored if score <= MAX_SUGGESTION_DISTANCE][:MAX_SUGGESTIONS]


# what building a route from its words may raise, each turned into a ConfigError at the route
ROUTE_ERRORS = (ValueError, OSError, IndexError, KeyError, TypeError)
