"""describe.py

What the configuration accepts, told from the same tree the engine reads with: the syntax
reference, the help of one keyword, and the data model with its JSON Schema and YANG module.

Copyright (c) 2009-2026 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import copy
import functools
import textwrap
from collections import Counter
from dataclasses import dataclass, field, replace
from typing import Any

from exabgp.configuration.grammar import json_schema, shape, yang
from exabgp.configuration.grammar.context import PrintContext
from exabgp.configuration.grammar.engine import MAX_DEPTH
from exabgp.configuration.grammar.nodes import MISSING, Block, Collect, Keep, Leaf
from exabgp.configuration.grammar.render import INDENT
from exabgp.configuration.grammar.shape import Kind, Shape
from exabgp.configuration.grammar.types.base import spoken


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


def locate(root: Block, path: list[str]) -> Block | Leaf:
    """The section or the statement reached by the keywords of `path`, ValueError when there is none.

    A keyword both a statement and a section (`route`) is the section: its statements are
    the values the one-line form takes too.
    """
    node: Block | Leaf = root
    for index, keyword in enumerate(path[:MAX_DEPTH]):
        if isinstance(node, Leaf):
            raise ValueError(f"'{path[index - 1]}' is a statement, it has no '{keyword}'")
        child = node.block(keyword) or node.leaf(keyword)
        if child is None:
            known = ', '.join(each.keyword for each in node.children)
            raise ValueError(f"no keyword '{keyword}' in {node.keyword or 'the configuration'}, only: {known}")
        node = child
    return node


def _statement(root: Block, path: list[str]) -> Leaf:
    """The statement at `path`: of a keyword both a statement and a section, the statement."""
    parent = locate(root, path[:-1])
    found = parent.leaf(path[-1]) if path and isinstance(parent, Block) else None
    if found is None:
        locate(root, path)  # the error naming what is wrong
        raise ValueError(f"'{path[-1] if path else 'the configuration'}' is a section, not a statement")
    return found


# a help shows a few of the spellings a value takes; the syntax line says what they have in common
MAX_HELP_EXAMPLES = 3


def _given(path: list[str]) -> Any:
    """What a neighbor holds for the statement at `path` when it is not there, None if nothing."""
    given: Any = {'neighbor': neighbor_defaults(), 'template': {'neighbor': neighbor_defaults()}}
    for keyword in path:
        given = given.get(keyword) if isinstance(given, dict) else None
    return given


def statement_help(root: Block, path: list[str]) -> list[str]:
    """The help of the statement at `path`: its syntax line, what it is for, its default, examples."""
    leaf = _statement(root, path)
    member = _leaf(leaf, _given(path))
    hint = leaf.type.hint()
    lines = [' '.join([*path[:-1], f'{leaf.keyword} {hint};' if hint else f'{leaf.keyword};'])]
    notes = [leaf.doc] if leaf.doc else []
    if member is None:
        notes.append('refused here')
    if leaf.mandatory:
        notes.append('mandatory')
    if member is not None and member.default is not None:
        notes.append(f'default {member.default}')
    if leaf.many or leaf.adds:
        notes.append('may be repeated')
    examples = [example for example in leaf.type.examples() if example][:MAX_HELP_EXAMPLES]
    notes.extend(f'example: {leaf.keyword} {example};' for example in examples)
    return lines + [INDENT + note for note in notes]


def statement_schema(root: Block, path: list[str]) -> dict[str, Any]:
    """The JSON Schema of the value of the statement at `path`."""
    leaf = _statement(root, path)
    member = _leaf(leaf, _given(path))
    if member is None:
        raise ValueError(f"'{path[-1]}' is refused here, it holds no value")
    return json_schema.schema(member, {})


def _leaf_line(leaf: Leaf) -> str:
    notes = [leaf.doc] if leaf.doc else []
    if leaf.mandatory:
        notes.append('mandatory')
    if leaf.default is not MISSING and leaf.default is not None:
        notes.append(f'default {spoken(leaf.type.render(leaf.default)) or leaf.default}')
    if leaf.many or leaf.adds:
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
            # a keyword only there to be refused (`endpoint` in l2vpn) is no statement to show
            if child.type.shape().kind != Kind.REFUSED:
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


MANUAL_INDENT = '    '  # a tab in a man page literal block is eight columns


def manual(lines: list[str], width: int) -> list[str]:
    """The syntax as a man page shows it: spaces for tabs, a note too wide above its statement."""
    found: list[str] = []
    for line in lines:
        depth = len(line) - len(line.lstrip(INDENT))
        text = line[depth:]
        indent = MANUAL_INDENT * depth
        statement, marker, note = text.partition('  # ')
        if len(indent + text) <= width:
            found.append(indent + text)
            continue
        if marker:
            found.extend(f'{indent}# {each}' for each in textwrap.wrap(note, width - len(indent) - 2))
        found.extend(_wrapped(statement, indent, width) if len(indent + statement) > width else [indent + statement])
    return found


def _wrapped(statement: str, indent: str, width: int) -> list[str]:
    """A statement too wide for a line, carried on lines indented further.

    It breaks at a space, or inside a word after a `|`: `unicast|multicast|...` has none.
    """
    pieces: list[tuple[str, str]] = []  # each piece, and what joins it to the one before
    for word in statement.split(' '):
        parts = word.split('|')
        pieces.append((parts[0] + ('|' if len(parts) > 1 else ''), ' '))
        pieces.extend((part + ('|' if index < len(parts) - 2 else ''), '') for index, part in enumerate(parts[1:]))
    lines = [indent]
    for piece, joint in pieces:
        room = width - len(lines[-1])
        if lines[-1].strip() and len(joint + piece) > room:
            lines.append(indent + MANUAL_INDENT * 2)
            joint = ''
        lines[-1] += (joint if lines[-1].strip() else '') + piece
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
    from exabgp.configuration.grammar.tree.codecs import neighbor_values

    _, values = neighbor_values(read_text(MINIMAL_NEIGHBOR).neighbors[0], PrintContext())
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
        default = spoken(leaf.type.render(implied)) or None
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
        # a section with needed statements means something by being there: role, tcp-ao
        present = any(isinstance(child, Leaf) and child.needed for child in block.children)
        return replace(shape.container(*fields, uses=uses), presence=present).described(block.doc)
    if block.name is None:
        return shape.leaf_list(shape.container(*fields, uses=uses)).described(block.doc)
    naming = block.name.shape().described(f'what the {block.keyword} is called, `{block.keyword} <{block.key}> {{`')
    requires = needed(block) if block.complete else ()
    item = shape.container((block.key, naming), *fields, uses=uses, requires=requires)
    return shape.keyed(item, block.key).described(block.doc)


def needed(block: Block, prefix: str = '', depth: int = 0) -> tuple[str, ...]:
    """The paths of the leaves a complete `block` must have (`local-as`, `role/local`)."""
    assert depth <= MAX_DEPTH, 'the tree is deeper than the engine reads'
    found: list[str] = []
    for child in block.children:
        if isinstance(child, Leaf):
            if child.needed:
                found.append(prefix + child.keyword)
        elif child.keep == Keep.SINGLE:
            found.extend(needed(child, f'{prefix}{child.keyword}/', depth + 1))
    return tuple(found)


def json_document(block: Block, title: str) -> dict[str, Any]:
    """The JSON Schema of what `block` reads, a copy the caller may change."""
    return copy.deepcopy(_json_document(block, title))


# the grammar tree is built once, at import, and never changes: nor does its schema, whose
# sharing of identical containers costs a tenth of a second
@functools.lru_cache(maxsize=64)
def _json_document(block: Block, title: str) -> dict[str, Any]:
    return json_schema.document(model(block), title)


def yang_module(block: Block) -> list[str]:
    """The YANG module of what `block` reads."""
    return yang.module(model(block), 'The configuration of ExaBGP, generated from the grammar which reads it.')
