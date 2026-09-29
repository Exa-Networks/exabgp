"""json_schema.py

The JSON Schema (2020-12) of the configuration, printed from its data model (shape.py).

A value is described as exabgp keeps it: a MED is an integer 0-4294967295, not the word
it was written as. A section used in several places (a neighbor and a template neighbor)
is declared once under `$defs` and referenced, and so is any container which comes out
the same in several places: the route values are the same in every announce family.

Copyright (c) 2009-2026 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import json
from collections import Counter
from typing import Any

from exabgp.configuration.grammar.shape import MAX_DEPTH, Kind, Shape, json_value

DIALECT = 'https://json-schema.org/draft/2020-12/schema'
SCHEMA_ID = 'https://github.com/Exa-Networks/exabgp/schema/configuration.json'

# a container smaller than this is left where it is: a reference would save next to nothing
SHARED_MIN_OCTETS = 256
# each pass moves one container to $defs, and there are far fewer distinct ones than this
MAX_SHARED = 1024


def document(root: Shape, title: str) -> dict[str, Any]:
    """The schema of a configuration whose data model is `root`."""
    defs: dict[str, Any] = {}
    body = schema(root, defs)
    header = {'$schema': DIALECT, '$id': SCHEMA_ID, 'title': title}
    found = {**header, **body, **({'$defs': defs} if defs else {})}
    share(found)
    return found


def share(document: dict[str, Any]) -> None:
    """Declare once, under `$defs`, every container which comes out the same in several places.

    The largest first, so a container inside a shared one is counted once, from `$defs`.
    """
    for _ in range(MAX_SHARED):
        counts: Counter[str] = Counter()
        names: dict[str, str] = {}
        _count(document, '', counts, names, 0)
        repeated = [text for text, count in counts.items() if count > 1]
        if not repeated:
            return
        text = max(repeated, key=len)
        name = _free_name(names[text], document.setdefault('$defs', {}))
        shared = json.loads(text)
        reference = {'$ref': f'#/$defs/{name}'}
        for key in list(document):
            document[key] = _replaced(document[key], shared, reference, 0)
        # after the replacement, which built a new $defs holding references where copies were
        document['$defs'][name] = shared
    raise RuntimeError(f'more than {MAX_SHARED} containers to share, the schema is not what it was')


def _count(node: Any, name: str, counts: Counter[str], names: dict[str, str], depth: int) -> None:
    """Count every container of at least SHARED_MIN_OCTETS, and name each after where it was met first."""
    assert depth <= MAX_DEPTH * 4, 'the schema nests deeper than its shape'
    if isinstance(node, list):
        for each in node:
            _count(each, name, counts, names, depth + 1)
        return
    if not isinstance(node, dict):
        return
    if 'properties' in node:
        text = json.dumps(node, sort_keys=True)
        if len(text) >= SHARED_MIN_OCTETS:
            counts[text] += 1
            names.setdefault(text, name)
    for key, each in node.items():
        # a $defs entry, a property and an item are named after the key which holds them
        inner = name if key in ('items', 'anyOf', 'oneOf', 'allOf', 'properties', '$defs') else key
        _count(each, inner, counts, names, depth + 1)


def _replaced(node: Any, shared: dict[str, Any], reference: dict[str, Any], depth: int) -> Any:
    assert depth <= MAX_DEPTH * 4, 'the schema nests deeper than its shape'
    if node == shared:
        return dict(reference)
    if isinstance(node, dict):
        return {key: _replaced(each, shared, reference, depth + 1) for key, each in node.items()}
    if isinstance(node, list):
        return [_replaced(each, shared, reference, depth + 1) for each in node]
    return node


def _free_name(wanted: str, defs: dict[str, Any]) -> str:
    base = wanted or 'shared'
    name, index = base, 1
    while name in defs:
        index += 1
        name = f'{base}-{index}'
    return name


def schema(shape: Shape, defs: dict[str, Any], depth: int = 0) -> dict[str, Any]:
    """The schema of a value of `shape`; named groupings are added to `defs` and referenced."""
    assert depth <= MAX_DEPTH, 'the shape nests deeper than any configuration'
    if shape.kind in (Kind.UNION, Kind.LIST, Kind.CONTAINER, Kind.CHOICE):
        found = _composite(shape, defs, depth)
    else:
        found = _scalar(shape)
    if shape.description:
        found['description'] = shape.description
    if shape.default is not None:
        found['default'] = json_value(shape, shape.default)
    return found


def _scalar(shape: Shape) -> dict[str, Any]:
    if shape.kind == Kind.INTEGER:
        bounds = [{'minimum': low, 'maximum': high} for low, high in shape.ranges]
        return {'type': 'integer', **bounds[0]} if len(bounds) == 1 else {'type': 'integer', 'anyOf': bounds}
    if shape.kind == Kind.BOOLEAN:
        return {'type': 'boolean'}
    if shape.kind == Kind.EMPTY:
        return {'type': 'null'}
    if shape.kind == Kind.ENUMERATION:
        return {'type': 'string', 'enum': list(shape.values)}
    assert shape.kind == Kind.STRING, f'{shape.kind} has no JSON Schema'
    found: dict[str, Any] = {'type': 'string'}
    if shape.pattern:
        found['pattern'] = f'^({shape.pattern})$'
    if len(shape.formats) == 1:
        found['format'] = shape.formats[0]
    elif shape.formats:
        found['anyOf'] = [{'format': each} for each in shape.formats]
    return found


def _composite(shape: Shape, defs: dict[str, Any], depth: int) -> dict[str, Any]:
    if shape.kind == Kind.UNION:
        return {'anyOf': [schema(member, defs, depth + 1) for member in shape.members]}
    if shape.kind == Kind.LIST:
        assert shape.item is not None
        found: dict[str, Any] = {'type': 'array', 'items': schema(shape.item, defs, depth + 1)}
        if shape.key:
            # the member naming an entry is always given
            found['items']['required'] = [shape.key, *found['items'].get('required', [])]
        if shape.min_items:
            found['minItems'] = shape.min_items
        if shape.max_items:
            found['maxItems'] = shape.max_items
        return found
    if shape.kind == Kind.CHOICE:
        cases = [_object(((name, case),), (), defs, depth + 1, required=[name]) for name, case in shape.fields]
        return {'oneOf': cases}
    found = _object(shape.fields, shape.uses, defs, depth + 1)
    _required(found, shape.requires)
    return found


def _object(
    fields: tuple[tuple[str, Shape], ...],
    uses: tuple[Shape, ...],
    defs: dict[str, Any],
    depth: int,
    required: list[str] | None = None,
) -> dict[str, Any]:
    found: dict[str, Any] = {'type': 'object', 'properties': {name: schema(each, defs, depth) for name, each in fields}}
    mandatory = (required or []) + [name for name, each in fields if each.mandatory]
    if mandatory:
        found['required'] = mandatory
    if not uses:
        found['additionalProperties'] = False
        return found
    for group in uses:
        if group.name not in defs:
            defs[group.name] = {}  # taken before it is filled: a grouping may not use itself
            defs[group.name] = _object(group.fields, group.uses, defs, depth + 1)
            # the members of a grouping are closed by the object using it
            defs[group.name].pop('additionalProperties', None)
    found['allOf'] = [{'$ref': f'#/$defs/{group.name}'} for group in uses]
    found['unevaluatedProperties'] = False
    return found


def _required(found: dict[str, Any], paths: tuple[str, ...]) -> None:
    """Add to `found` the members which must be there: `role/local` is local, when role is given."""
    for path in paths:
        *sections, name = path.split('/')
        target = found
        for section in sections:
            target = target.setdefault('properties', {}).setdefault(section, {})
        target.setdefault('required', []).append(name)
