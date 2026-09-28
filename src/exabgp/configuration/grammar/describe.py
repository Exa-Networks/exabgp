"""describe.py

What the configuration accepts, told from the same tree the engine reads with: the syntax
reference, the help of one keyword, and a JSON schema.

Copyright (c) 2009-2026 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from exabgp.configuration.grammar.engine import MAX_DEPTH
from exabgp.configuration.grammar.nodes import MISSING, Block, Keep, Leaf
from exabgp.configuration.grammar.render import INDENT


@dataclass(frozen=True)
class Help:
    """One keyword: what it is for, what it takes, and a value it accepts."""

    keyword: str
    doc: str
    hint: str
    example: str


def keyword_help(keyword: str, value: Any, doc: str = '') -> Help:
    """The help of a keyword taking a value of the type `value`."""
    examples = [example for example in value.examples() if example]
    return Help(keyword, doc, value.hint(), examples[0] if examples else '')


def route_help(keyword: str) -> Help | None:
    """The help of a keyword of a route (`next-hop`, `as-path`, ...), None for another word."""
    from exabgp.configuration.grammar.tree.static import ROUTE_VALUES

    spec = ROUTE_VALUES.get(keyword)
    return None if spec is None else keyword_help(keyword, spec.type, spec.doc)


def find(root: Block, path: list[str]) -> Block:
    """The block reached by the keywords of `path` from `root`, ValueError when there is none."""
    block = root
    for keyword in path[:MAX_DEPTH]:
        child = block.block(keyword)
        if child is None:
            known = ', '.join(each.keyword for each in block.blocks())
            raise ValueError(f"no section '{keyword}' in {block.keyword or 'the configuration'}, only: {known}")
        block = child
    return block


def _leaf_line(leaf: Leaf) -> str:
    notes = [leaf.doc] if leaf.doc else []
    if leaf.mandatory:
        notes.append('mandatory')
    if leaf.default is not MISSING and leaf.default is not None:
        notes.append(f'default {" ".join(leaf.type.render(leaf.default)) or leaf.default}')
    if leaf.repeated:
        notes.append('may be repeated')
    hint = leaf.type.hint()
    line = f'{leaf.keyword} {hint};' if hint else f'{leaf.keyword};'
    return f'{line}  # {", ".join(notes)}' if notes else line


def _opening(block: Block) -> str:
    name = f' {block.name.hint()}' if block.name is not None else ''
    note = f'  # {block.doc}' if block.doc else ''
    return f'{block.keyword}{name} {{{note}'


def syntax(block: Block, depth: int = 0, seen: dict[tuple[int, ...], str] | None = None) -> list[str]:
    """The syntax reference of `block`, one line per statement, sections indented.

    A section declared with the children of one already shown (a template neighbor) refers
    to it rather than repeating it.
    """
    assert depth <= MAX_DEPTH, 'the tree is deeper than the engine reads'
    seen = {} if seen is None else seen
    lines: list[str] = []
    for child in block.children:
        indent = INDENT * depth
        if isinstance(child, Leaf):
            lines.append(indent + _leaf_line(child))
            continue
        key = tuple(id(each) for each in child.children)
        if key in seen:
            lines.append(f'{indent}{_opening(child)[:-1]} ... }}  # as {seen[key]}')
            continue
        seen[key] = child.keyword
        lines.append(indent + _opening(child))
        lines.extend(syntax(child, depth + 1, seen))
        lines.append(indent + '}')
    return lines


def json_schema(block: Block, depth: int = 0) -> dict[str, Any]:
    """A JSON schema of the values of `block`, a section as an object, a leaf as its type."""
    assert depth <= MAX_DEPTH, 'the tree is deeper than the engine reads'
    properties: dict[str, Any] = {}
    for child in block.children:
        if isinstance(child, Leaf):
            value = {**child.type.json_schema(), 'description': child.doc} if child.doc else child.type.json_schema()
            properties[child.keyword] = {'type': 'array', 'items': value} if child.repeated else value
            continue
        inner = json_schema(child, depth + 1)
        if child.keep == Keep.NAMED:
            properties[child.keyword] = {'type': 'object', 'additionalProperties': inner}
        elif child.keep in (Keep.LIST, Keep.EXTEND):
            properties[child.keyword] = {'type': 'array', 'items': inner}
        else:
            properties[child.keyword] = inner
    schema: dict[str, Any] = {'type': 'object', 'properties': properties}
    if block.doc:
        schema['description'] = block.doc
    return schema
