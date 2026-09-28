"""yang.py

The YANG 1.1 module (RFC 7950) of the configuration, printed from its data model (shape.py).

    container   -> container
    keyed list  -> list with its key
    other list  -> leaf-list of a value, or a list keyed by `index`, the position of the entry
                   (a configuration list must have a key in YANG)
    choice      -> choice, one case per alternative, each a container named by it
    value       -> leaf, typed with the YANG built-in or the ietf-inet-types typedef

A section used in several places is a grouping, and `uses` where it is used.

Copyright (c) 2009-2026 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from exabgp.configuration.grammar.shape import (
    INT64_MAX,
    INT64_MIN,
    MAX_DEPTH,
    UINT8_MAX,
    UINT16_MAX,
    UINT32_MAX,
    UINT64_MAX,
    Kind,
    Shape,
)

MODULE = 'exabgp-configuration'
NAMESPACE = 'urn:exa-networks:exabgp:configuration'
PREFIX = 'exabgp'
INDENT = '  '
INDEX = 'index'  # the key of a list whose entries have no name of their own

_INTEGER_BOUNDS = {
    'uint8': (0, UINT8_MAX),
    'uint16': (0, UINT16_MAX),
    'uint32': (0, UINT32_MAX),
    'uint64': (0, UINT64_MAX),
    'int64': (INT64_MIN, INT64_MAX),
}


def module(root: Shape, description: str) -> list[str]:
    """The lines of the module whose data nodes are the members of `root`."""
    assert root.kind == Kind.CONTAINER
    groupings: dict[str, list[str]] = {}
    body: list[str] = []
    for name, each in root.fields:
        body.extend(node(name, each, INDENT, groupings))
    header = [
        f'module {MODULE} {{',
        f'{INDENT}yang-version 1.1;',
        f'{INDENT}namespace {quote(NAMESPACE)};',
        f'{INDENT}prefix {PREFIX};',
        f'{INDENT}import ietf-inet-types {{',
        f'{INDENT * 2}prefix inet;',
        f'{INDENT * 2}reference {quote("RFC 6991")};',
        f'{INDENT}}}',
        f'{INDENT}organization {quote("Exa Networks")};',
        f'{INDENT}description {quote(description)};',
    ]
    return header + [line for lines in groupings.values() for line in lines] + body + ['}']


def node(name: str, shape: Shape, indent: str, groupings: dict[str, list[str]], depth: int = 0) -> list[str]:
    """The data node `name` holding a value of `shape`."""
    assert depth <= MAX_DEPTH, 'the shape nests deeper than any configuration'
    if shape.kind == Kind.CONTAINER:
        return _statement('container', name, shape, indent, _members(shape, indent + INDENT, groupings, depth))
    if shape.kind == Kind.CHOICE:
        return _choice(name, shape, indent, groupings, depth)
    if shape.kind == Kind.LIST:
        return _list(name, shape, indent, groupings, depth)
    lines = type_statement(shape, indent + INDENT)
    if shape.mandatory:
        lines.append(f'{indent}{INDENT}mandatory true;')
    elif shape.default is not None:
        lines.append(f'{indent}{INDENT}default {quote(shape.default)};')
    return _statement('leaf', name, shape, indent, lines)


def _statement(keyword: str, name: str, shape: Shape, indent: str, inner: list[str]) -> list[str]:
    described = [f'{indent}{INDENT}description {quote(shape.description)};'] if shape.description else []
    return [f'{indent}{keyword} {name} {{', *described, *inner, f'{indent}}}']


def _members(shape: Shape, indent: str, groupings: dict[str, list[str]], depth: int) -> list[str]:
    lines: list[str] = []
    for group in shape.uses:
        if group.name not in groupings:
            groupings[group.name] = []  # taken before it is filled: a grouping may not use itself
            inner = _members(group, INDENT * 2, groupings, depth + 1)
            groupings[group.name] = [f'{INDENT}grouping {group.name} {{', *inner, f'{INDENT}}}']
        lines.append(f'{indent}uses {group.name};')
    for name, each in shape.fields:
        lines.extend(node(name, each, indent, groupings, depth + 1))
    return lines


def _choice(name: str, shape: Shape, indent: str, groupings: dict[str, list[str]], depth: int) -> list[str]:
    cases: list[str] = []
    for case, each in shape.fields:
        inner = node(case, each, indent + INDENT * 2, groupings, depth + 1)
        cases.extend([f'{indent}{INDENT}case {case} {{', *inner, f'{indent}{INDENT}}}'])
    return _statement('choice', name, shape, indent, cases)


def _list(name: str, shape: Shape, indent: str, groupings: dict[str, list[str]], depth: int) -> list[str]:
    item = shape.item
    assert item is not None
    bounds = [f'{indent}{INDENT}min-elements {shape.min_items};'] if shape.min_items else []
    if shape.max_items:
        bounds.append(f'{indent}{INDENT}max-elements {shape.max_items};')
    if item.kind not in (Kind.CONTAINER, Kind.CHOICE, Kind.LIST):
        return _statement('leaf-list', name, shape, indent, [*type_statement(item, indent + INDENT), *bounds])
    inner = indent + INDENT
    if shape.key:
        head = [f'{inner}key {quote(shape.key)};']
    else:
        index = [f'{inner}leaf {INDEX} {{', f'{inner}{INDENT}type uint32;']
        index += [f'{inner}{INDENT}description {quote("the position of the entry")};', f'{inner}}}']
        head = [f'{inner}key {quote(INDEX)};', f'{inner}ordered-by user;', *index]
    if item.kind == Kind.CONTAINER:
        body = _members(item, inner, groupings, depth + 1)
    else:
        body = node('value', item, inner, groupings, depth + 1)
    return _statement('list', name, shape, indent, [*head, *bounds, *body])


def type_statement(shape: Shape, indent: str) -> list[str]:
    """The `type` statement of a leaf holding a value of `shape`."""
    if shape.typedef:
        return [f'{indent}type {shape.typedef};']
    if shape.kind == Kind.INTEGER:
        return _integer(shape, indent)
    if shape.kind in (Kind.BOOLEAN, Kind.EMPTY):
        return [f'{indent}type {shape.kind.value};']
    if shape.kind == Kind.ENUMERATION:
        enums = [f'{indent}{INDENT}enum {quote(value)};' for value in shape.values]
        return [f'{indent}type enumeration {{', *enums, f'{indent}}}']
    if shape.kind == Kind.UNION:
        members = [line for each in shape.members for line in type_statement(each, indent + INDENT)]
        return [f'{indent}type union {{', *members, f'{indent}}}']
    assert shape.kind == Kind.STRING, f'{shape.kind} is not the type of a leaf'
    if not shape.pattern:
        return [f'{indent}type string;']
    return [f'{indent}type string {{', f'{indent}{INDENT}pattern {quote(shape.pattern)};', f'{indent}}}']


def _integer(shape: Shape, indent: str) -> list[str]:
    low = min(first for first, _ in shape.ranges)
    high = max(last for _, last in shape.ranges)
    base = next(name for name, (first, last) in _INTEGER_BOUNDS.items() if first <= low and high <= last)
    if shape.ranges == (_INTEGER_BOUNDS[base],):
        return [f'{indent}type {base};']
    ranges = ' | '.join(str(first) if first == last else f'{first}..{last}' for first, last in shape.ranges)
    return [f'{indent}type {base} {{', f'{indent}{INDENT}range {quote(ranges)};', f'{indent}}}']


def quote(text: str) -> str:
    """A YANG string: single quoted keeps every character but the single quote itself."""
    if "'" not in text:
        return f"'{text}'"
    return '"' + text.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n') + '"'
