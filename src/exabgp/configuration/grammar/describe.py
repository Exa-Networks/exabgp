"""describe.py

What the configuration accepts, told from the same tree the engine reads with: the syntax
reference, the help of one keyword, and the data model with its JSON Schema and YANG module.

Copyright (c) 2009-2026 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from exabgp.configuration.grammar import json_schema, shape, yang
from exabgp.configuration.grammar.engine import MAX_DEPTH
from exabgp.configuration.grammar.nodes import MISSING, Block, Collect, Keep, Leaf
from exabgp.configuration.grammar.shape import Kind, Shape
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


# --------------------------------------------------------------------------- the data model


def model(root: Block) -> Shape:
    """The data model of what `root` reads (shape.py), for the JSON Schema and the YANG module.

    A keyword which is both a statement and a section (`route <prefix> ...;` and `route
    <prefix> { ... }`) is one node: two ways of writing the same entries. A section whose
    statements are those of another (a template neighbor, a neighbor) is one grouping.
    """
    shared = {key for key, count in _sections(root, Counter(), 0).items() if count > 1}
    defaults = neighbor_defaults()
    return shape.container(
        *_fields(root, _Build(shared), {'neighbor': defaults, 'template': {'neighbor': defaults}}, 0)
    )


# a neighbor with only the statements it must have: what it holds for the others is their default
MINIMAL_NEIGHBOR = 'neighbor 127.0.0.1 { local-address 127.0.0.1; local-as 65001; peer-as 65002; router-id 10.0.0.1; }'
GIVEN = frozenset({'local-address', 'local-as', 'peer-as', 'router-id'})


def neighbor_defaults() -> dict[str, Any]:
    """The value of each statement a neighbor is not given, by keyword, as the neighbor prints it.

    The defaults are applied where a neighbor is made (tree/resolve.py), not by the engine: a
    template would otherwise give its defaults over what the neighbor says. They are read
    back from a neighbor, so they are never written twice.
    """
    from exabgp.configuration.grammar.read import read_text
    from exabgp.configuration.grammar.tree.unresolve import neighbor_values

    _, values = neighbor_values(read_text(MINIMAL_NEIGHBOR).neighbors[0], {})
    return {keyword: value for keyword, value in values.items() if keyword not in GIVEN}


def _sections(block: Block, counts: Counter[tuple[int, ...]], depth: int) -> Counter[tuple[int, ...]]:
    assert depth <= MAX_DEPTH, 'the tree is deeper than the engine reads'
    for child in block.blocks():
        counts[_statements(child)] += 1
        # the sections of a section seen already come with it
        if counts[_statements(child)] == 1:
            _sections(child, counts, depth + 1)
    return counts


def _statements(block: Block) -> tuple[int, ...]:
    return tuple(id(child) for child in block.children)


@dataclass
class _Build:
    shared: set[tuple[int, ...]]  # the sections used in several places
    groups: dict[tuple[int, ...], Shape] = field(default_factory=dict)  # their groupings, once made


def _fields(block: Block, build: _Build, defaults: dict[str, Any], depth: int) -> tuple[tuple[str, Shape], ...]:
    fields: list[tuple[str, Shape]] = []
    for child in block.children:
        given = defaults.get(child.keyword)
        if isinstance(child, Block):
            inner = given if isinstance(given, dict) else {}
            fields.append((child.keyword, _section(child, build, inner, depth + 1)))
        elif block.block(child.keyword) is None and (value := _leaf(child, given)) is not None:
            fields.append((child.keyword, value))
    return tuple(fields)


def _leaf(leaf: Leaf, given: Any) -> Shape | None:
    """The member a statement fills, None for a keyword only there to be refused.

    `given` is the value a neighbor holds when the statement is not there.
    """
    value = leaf.type.shape()
    if value.kind == Kind.REFUSED:
        return None
    if leaf.many and not (leaf.collect == Collect.EXTEND and value.kind == Kind.LIST):
        value = shape.leaf_list(value)
    implied = leaf.default if leaf.default is not MISSING else given
    default = None
    if implied is not None and not leaf.many:
        default = ' '.join(leaf.type.render(implied)) or None
    return shape.member(value, mandatory=leaf.mandatory, default=default, description=leaf.doc)


def _section(block: Block, build: _Build, defaults: dict[str, Any], depth: int) -> Shape:
    assert depth <= MAX_DEPTH, 'the tree is deeper than the engine reads'
    fields = _fields(block, build, defaults, depth)
    uses: tuple[Shape, ...] = ()
    key = _statements(block)
    if key in build.shared:
        if key not in build.groups:
            names = {group.name for group in build.groups.values()}
            name = block.keyword if block.keyword not in names else f'{block.keyword}-{len(build.groups)}'
            build.groups[key] = shape.grouping(name, *fields)
        fields, uses = (), (build.groups[key],)
    if block.keep == Keep.SINGLE:
        return shape.container(*fields, uses=uses).described(block.doc)
    if block.name is None:
        return shape.leaf_list(shape.container(*fields, uses=uses)).described(block.doc)
    naming = block.name.shape().described(f'what the {block.keyword} is called, `{block.keyword} <{block.key}> {{`')
    item = shape.container((block.key, naming), *fields, uses=uses)
    return shape.keyed(item, block.key).described(block.doc)


def json_document(block: Block, title: str) -> dict[str, Any]:
    """The JSON Schema of what `block` reads."""
    return json_schema.document(model(block), title)


def yang_module(block: Block) -> list[str]:
    """The YANG module of what `block` reads."""
    return yang.module(model(block), 'The configuration of ExaBGP, generated from the grammar which reads it.')
