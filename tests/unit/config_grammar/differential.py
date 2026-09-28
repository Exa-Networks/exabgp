"""Read one configuration with both parsers: the helpers of exabgp.configuration.compare, returning outcomes only.

Copyright (c) 2009-2026 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from exabgp.configuration import compare
from exabgp.configuration.compare import Accepted, Outcome, Rejected, agree

__all__ = ['Accepted', 'Outcome', 'Rejected', 'agree', 'grammar', 'grammar_file', 'legacy', 'legacy_file']


def legacy(text: str) -> Outcome:
    return compare.legacy_text(text)[0]


def legacy_file(path: str) -> Outcome:
    return compare.legacy_file(path)[0]


def grammar(text: str) -> Outcome:
    return compare.grammar_text(text)[0]


def grammar_file(path: str) -> Outcome:
    return compare.grammar_file(path)[0]
