"""example.py

A documented configuration, generated from the grammar: `exabgp configuration example`.

The statements a neighbor must have are given, so the file is a configuration exabgp reads;
every other statement and section is written commented out, with what it is for, what it
takes, and its default or a value it accepts.

Copyright (c) 2009-2026 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from typing import Any

from exabgp.configuration.grammar.describe import neighbor_defaults
from exabgp.configuration.grammar.engine import MAX_DEPTH
from exabgp.configuration.grammar.nodes import MISSING, Block, Leaf
from exabgp.configuration.grammar.shape import Kind

INDENT = '    '
RULE = '# ' + '=' * 77
PEER = '127.0.0.1'
# the statements a neighbor must have, given so the example is read
GIVEN = {'local-address': '127.0.0.1', 'local-as': '65000', 'peer-as': '65001', 'router-id': '127.0.0.1'}

HEADER = [
    RULE,
    '# EXABGP CONFIGURATION EXAMPLE',
    RULE,
    '# Generated from the configuration grammar',
    '# This file documents all available configuration options',
    '#',
    '# Usage: ./sbin/exabgp configuration example > example.conf',
    '#        ./sbin/exabgp configuration validate example.conf',
    RULE,
    '',
    RULE,
    '# NEIGHBOR CONFIGURATION',
    RULE,
]


def example() -> str:
    """The documented neighbor configuration."""
    from exabgp.configuration.grammar.tree.neighbor import NEIGHBOR

    lines = [*HEADER, f'# {NEIGHBOR.doc}', '', f'neighbor {PEER} {{']
    lines.extend(_children(NEIGHBOR, neighbor_defaults(), INDENT, given=True, depth=0))
    return '\n'.join([*lines, '}', ''])


def _children(block: Block, defaults: dict[str, Any], indent: str, given: bool, depth: int) -> list[str]:
    assert depth <= MAX_DEPTH, 'the tree is deeper than the engine reads'
    lines: list[str] = []
    for child in block.children:
        if isinstance(child, Leaf):
            lines.extend(_leaf(child, defaults.get(child.keyword), indent, given))
            continue
        inner = defaults.get(child.keyword)
        name = f' {_first(child.name.examples())}' if child.name is not None else ''
        doc = [f'{indent}# {child.keyword}: {child.doc}'] if child.doc else []
        lines.extend(['', *doc, f'{indent}# {child.keyword}{name} {{'])
        lines.extend(_children(child, inner if isinstance(inner, dict) else {}, indent + INDENT, False, depth + 1))
        lines.append(f'{indent}# }}')
    return lines


def _leaf(leaf: Leaf, default: Any, indent: str, given: bool) -> list[str]:
    if leaf.type.shape().kind == Kind.REFUSED:
        return []
    implied = leaf.default if leaf.default is not MISSING else default
    value = ' '.join(leaf.type.render(implied)) if implied is not None and not leaf.many else ''
    lines = ['', f'{indent}# {leaf.keyword}: {leaf.doc}' if leaf.doc else f'{indent}# {leaf.keyword}']
    if leaf.type.hint():
        lines.append(f'{indent}# Type: {leaf.type.hint()}')
    if value:
        lines.append(f'{indent}# Default: {value}')
    if given and leaf.keyword in GIVEN:
        return [*lines, f'{indent}{leaf.keyword} {GIVEN[leaf.keyword]};']
    shown = value or _first(leaf.type.examples())
    return [*lines, f'{indent}# {leaf.keyword} {shown};' if shown else f'{indent}# {leaf.keyword};']


def _first(examples: list[str]) -> str:
    return next((each for each in examples if each), '')
