"""yang.py

The YANG 1.1 module (RFC 7950) of the configuration, printed from its data model (shape.py).

    container   -> container
    keyed list  -> list with its key
    other list  -> leaf-list of a value, or a list keyed by `index`, the position of the entry
                   (a configuration list must have a key in YANG)
    choice      -> choice, one case per alternative, each a container named by it
    value       -> leaf, typed with the YANG built-in or the ietf-inet-types typedef

A section used in several places is a grouping, and `uses` where it is used; so is a
container whose members come out the same in several places, as the route values do in
every announce family.

Copyright (c) 2009-2026 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from collections import Counter

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
    grouping,
    replaced,
)

MODULE = 'exabgp-configuration'
NAMESPACE = 'urn:exa-networks:exabgp:configuration'
PREFIX = 'exabgp'
INDENT = '  '
INDEX = 'index'  # the key of a list whose entries have no name of their own

# a repeated container printing fewer lines than this is left where it is
SHARED_MIN_LINES = 8

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
    root = share(root)
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
        present = [f'{indent}{INDENT}presence {quote("the section is given")};'] if shape.presence else []
        return _statement(
            'container', name, shape, indent, [*present, *_members(shape, indent + INDENT, groupings, depth)]
        )
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
        if shape.requires:
            refines = [f'{indent}{INDENT}refine {quote(path)} {{ mandatory true; }}' for path in shape.requires]
            lines.extend([f'{indent}uses {group.name} {{', *refines, f'{indent}}}'])
        else:
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


# --------------------------------------------------------------------------- sharing


Members = tuple[tuple[str, Shape], ...]


class _Sharing:
    """What share() needs as it walks the model: the counts, and the groupings made so far."""

    def __init__(self, counts: Counter[Members], names: dict[Members, str], taken: set[str]) -> None:
        # the members of a container, or one list member alone, as it is printed in each place
        self.counts = counts
        self.names = names
        self.taken = taken
        self.groups: dict[tuple[Members, str], Shape] = {}
        self.rewritten: dict[str, Shape] = {}  # the groupings of the model, each rewritten once

    def name(self, members: Members) -> str:
        base = self.names.get(members) or 'shared'
        name, index = base, 1
        while name in self.taken:
            index += 1
            name = f'{base}-{index}'
        self.taken.add(name)
        return name


def share(root: Shape) -> Shape:
    """`root`, with every container whose members are the same in several places made a grouping."""
    counts: Counter[Members] = Counter()
    names: dict[Members, str] = {}
    taken: set[str] = set()
    _count(root, '', counts, names, taken, 0)
    return _shared(root, _Sharing(counts, names, taken), '', 0)


def _count(
    shape: Shape, name: str, counts: Counter[Members], names: dict[Members, str], seen: set[str], depth: int
) -> None:
    """Count the members of every container as printed: a grouping of the model is printed once."""
    assert depth <= MAX_DEPTH * 2, 'the shape nests deeper than any configuration'
    if shape.kind == Kind.CONTAINER and shape.fields:
        counts[shape.fields] += 1
        names.setdefault(shape.fields, name)
        for member in shape.fields:
            if member[1].kind == Kind.LIST:
                counts[(member,)] += 1
                names.setdefault((member,), member[0])
    for group in shape.uses:
        if group.name not in seen:
            seen.add(group.name)
            _count(group, group.name, counts, names, seen, depth + 1)
    for inner, each in shape.fields:
        _count(each, inner, counts, names, seen, depth + 1)
    for each in shape.members:
        _count(each, name, counts, names, seen, depth + 1)
    if shape.item is not None:
        _count(shape.item, name, counts, names, seen, depth + 1)


def _shared(shape: Shape, sharing: _Sharing, key: str, depth: int) -> Shape:
    """`shape` rewritten from its leaves up; `key` is the member naming it, as the entry of a list."""
    assert depth <= MAX_DEPTH * 2, 'the shape nests deeper than any configuration'
    if shape.kind not in (Kind.CONTAINER, Kind.CHOICE, Kind.LIST, Kind.UNION):
        return shape
    fields = tuple((name, _shared(each, sharing, '', depth + 1)) for name, each in shape.fields)
    members = tuple(_shared(each, sharing, '', depth + 1) for each in shape.members)
    item = _shared(shape.item, sharing, shape.key, depth + 1) if shape.item is not None else None
    uses = tuple(_group(group, sharing, depth + 1) for group in shape.uses)
    if shape.kind == Kind.CONTAINER:
        fields, uses = _lists_shared(shape.fields, fields, uses, sharing)
    found = replaced(shape, fields=fields, members=members, item=item, uses=uses)
    if not _worth_sharing(shape, found, sharing):
        return found
    # a list key must be a member of the list itself, so it stays out of the grouping
    inline = tuple((name, each) for name, each in fields if name == key)
    group = sharing.groups.get((shape.fields, key))
    if group is None:
        group = grouping(sharing.name(shape.fields), *(member for member in fields if member[0] != key))
        sharing.groups[(shape.fields, key)] = group
    return replaced(found, fields=inline, uses=(*uses, group))


def _lists_shared(
    original: Members, fields: Members, uses: tuple[Shape, ...], sharing: _Sharing
) -> tuple[Members, tuple[Shape, ...]]:
    """A list printed the same in several containers goes, whole, into a grouping of its own."""
    kept: list[tuple[str, Shape]] = []
    for before, after in zip(original, fields):
        alone = (before,)
        if after[1].kind != Kind.LIST or sharing.counts[alone] < 2:
            kept.append(after)
            continue
        if len(node(after[0], after[1], '', {}, 0)) < SHARED_MIN_LINES:
            kept.append(after)
            continue
        group = sharing.groups.get((alone, ''))
        if group is None:
            group = grouping(sharing.name(alone), after)
            sharing.groups[(alone, '')] = group
        uses = (*uses, group)
    return tuple(kept), uses


def _worth_sharing(shape: Shape, found: Shape, sharing: _Sharing) -> bool:
    if shape.kind != Kind.CONTAINER or sharing.counts[shape.fields] < 2:
        return False
    # the paths a container refines are its own, they would not name the members of a grouping
    if shape.requires or shape.name:
        return False
    return len(_members(found, '', {}, 0)) >= SHARED_MIN_LINES


def _group(group: Shape, sharing: _Sharing, depth: int) -> Shape:
    """A grouping of the model, rewritten once, so every `uses` names the same one."""
    if group.name not in sharing.rewritten:
        fields = tuple((name, _shared(each, sharing, '', depth + 1)) for name, each in group.fields)
        sharing.rewritten[group.name] = replaced(group, fields=fields)
    return sharing.rewritten[group.name]
