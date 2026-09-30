"""The data model of the configuration (grammar/shape.py) says what the parser reads.

Each value type declares what its value is once: a number declares its ranges, and the
check, the hint, the JSON Schema and the YANG type come from them. These tests hold the
declarations to the parser, and check the JSON Schema and the YANG module are well formed
without any third party validator.
"""

from __future__ import annotations

import gc
import json
import re
from typing import Any, Iterator

import pytest

from exabgp.configuration.grammar import shape as model_shapes
from exabgp.configuration.grammar.describe import json_document, model, yang_module
from exabgp.configuration.grammar.lexer import lex_text
from exabgp.configuration.grammar.nodes import Block, Leaf
from exabgp.configuration.grammar.shape import Kind, Shape, accepts
from exabgp.configuration.grammar.tree.root import ROOT
from exabgp.configuration.grammar.types.word import Number
from exabgp.configuration.grammar.words import Words

MAX_DEPTH = 40


def _numbers() -> list[Number[Any]]:
    """Every Number the grammar declares, wherever it is used."""
    # Compiled ABCs share an inherited cache: isinstance can find unrelated objects after
    # another class check. Inspect inheritance only for discovery, then exercise parsing.
    found = {id(each): each for each in gc.get_objects() if Number in type(each).__mro__}
    return sorted(found.values(), key=lambda each: (each.name, each.ranges))


def _words(text: str) -> Words:
    statement = lex_text(f'keyword {text};')[0]
    return Words(tuple(statement.words[1:]), statement.tokens[-1])


def _reads(number: Number[Any], value: int) -> bool:
    try:
        number.parse(_words(str(value)))
    except ValueError:
        return False
    return True


@pytest.mark.parametrize('number', _numbers(), ids=lambda number: f'{number.name}{number.ranges}')
def test_a_number_reads_what_its_ranges_say(number: Number[Any]) -> None:
    for low, high in number.ranges:
        assert _reads(number, low), f'{number.name} refuses {low}, its lowest'
        assert _reads(number, high), f'{number.name} refuses {high}, its highest'
        for outside in (low - 1, high + 1):
            if not any(first <= outside <= last for first, last in number.ranges):
                assert not _reads(number, outside), f'{number.name} reads {outside}, outside {number.ranges}'


def test_the_numbers_were_found() -> None:
    names = {number.name for number in _numbers()}
    assert {'med', 'local-preference', 'hold-time', 'as-number', 'port'} <= names


# --------------------------------------------------------------------------- the model


def _members(value: Shape, path: str, depth: int = 0) -> Iterator[tuple[str, Shape]]:
    """Every value of the model, by its path, the members of groupings under their use."""
    assert depth < MAX_DEPTH
    yield path, value
    for group in value.uses:
        yield from _members(model_shapes.container(*group.fields), path, depth + 1)
    for name, each in value.fields:
        yield from _members(each, f'{path}/{name}', depth + 1)
    for index, each in enumerate(value.members):
        yield from _members(each, f'{path}|{index}', depth + 1)
    if value.item is not None:
        yield from _members(value.item, f'{path}[]', depth + 1)


# the keywords whose value is text: a name, a password, a program, a regular expression
TEXT = frozenset(
    {
        'description',
        'host-name',
        'domain-name',
        'md5-password',
        'password',
        'source-interface',
        'processes',
        'processes-match',
        'name',
        'label',
        'watchdog',
        'policy-name',
        'candidate-path-name',
        'advisory',
        'run',
    }
)


def _keyword(path: str) -> str:
    return re.split(r'[/|\[\]]+', path.rstrip('[]|0123456789'))[-1]


def test_no_value_is_a_plain_string_but_text() -> None:
    plain = [
        path
        for path, value in _members(model(ROOT), '')
        if value.kind == Kind.STRING and not (value.pattern or value.formats or value.typedef)
    ]
    assert plain
    assert [path for path in plain if _keyword(path) not in TEXT] == []


def test_med_is_a_number() -> None:
    values = dict(_members(model(ROOT), ''))
    med = values['/neighbor[]/static/route[]/med']
    assert med.kind == Kind.INTEGER and med.ranges == ((0, 0xFFFFFFFF),)


def _leaves(block: Block, depth: int = 0) -> Iterator[Leaf]:
    assert depth < MAX_DEPTH
    for child in block.children:
        if isinstance(child, Leaf):
            yield child
        else:
            yield from _leaves(child, depth + 1)


def _printed(leaf: Leaf) -> Iterator[tuple[str, str]]:
    """Each example of a one word value, with the word it prints back as."""
    for example in leaf.type.examples():
        try:
            rendered = leaf.type.render(leaf.type.parse(_words(example)))
        except ValueError:
            continue  # read in the context of a route or a flow, checked by the corpus
        if len(rendered) == 1 and ' ' not in rendered[0]:
            yield example, rendered[0]


# printed as the statement writes it, not as the value is: `split /24` is the length 24
PRINTED_OTHERWISE = frozenset({'split'})


def test_what_a_value_prints_is_a_value_of_its_model() -> None:
    wrong = []
    seen: set[int] = set()
    for leaf in _leaves(ROOT):
        value = leaf.type.shape()
        if id(leaf.type) in seen or leaf.keyword in PRINTED_OTHERWISE or value.kind in (Kind.LIST, Kind.CONTAINER):
            continue
        seen.add(id(leaf.type))
        wrong.extend(
            f'{leaf.keyword} {example!r} prints {word!r}'
            for example, word in _printed(leaf)
            if not accepts(value, word)
        )
    assert wrong == []


# --------------------------------------------------------------------------- JSON Schema

SCHEMA_KEYWORDS = frozenset(
    {
        '$schema', '$id', '$defs', '$ref', 'title', 'description', 'type', 'properties', 'required',
        'additionalProperties', 'unevaluatedProperties', 'items', 'minItems', 'maxItems', 'enum',
        'minimum', 'maximum', 'pattern', 'format', 'anyOf', 'oneOf', 'allOf', 'default',
    }
)  # fmt: skip
TYPES = frozenset({'object', 'array', 'string', 'integer', 'boolean', 'null'})


def _schemas(schema: dict[str, Any], depth: int = 0) -> Iterator[dict[str, Any]]:
    assert depth < MAX_DEPTH
    yield schema
    for key in ('properties', '$defs'):
        for each in schema.get(key, {}).values():
            yield from _schemas(each, depth + 1)
    for key in ('anyOf', 'oneOf', 'allOf'):
        for each in schema.get(key, []):
            yield from _schemas(each, depth + 1)
    for key in ('items', 'additionalProperties'):
        if isinstance(schema.get(key), dict):
            yield from _schemas(schema[key], depth + 1)


def test_the_json_schema_is_well_formed() -> None:
    document = json_document(ROOT, 'ExaBGP configuration')
    assert document['$schema'] == 'https://json-schema.org/draft/2020-12/schema'
    for each in _schemas(document):
        assert set(each) <= SCHEMA_KEYWORDS, set(each) - SCHEMA_KEYWORDS
        assert each.get('type', 'object') in TYPES
        if 'pattern' in each:
            re.compile(each['pattern'])
        if '$ref' in each:
            assert each['$ref'].removeprefix('#/$defs/') in document['$defs']
        # an object which only adds `required` to one a grouping defines has no properties of its own
        if 'required' in each and 'allOf' not in each and 'properties' in each:
            assert set(each['required']) <= set(each['properties']), each['required']
        if 'minimum' in each:
            assert each['minimum'] <= each['maximum']


def _dereferenced(document: dict[str, Any], schema: dict[str, Any]) -> dict[str, Any]:
    """The schema itself, or the one of `$defs` it is only a reference to."""
    while set(schema) == {'$ref'}:
        schema = document['$defs'][schema['$ref'].removeprefix('#/$defs/')]
    return schema


def _at(document: dict[str, Any], schema: dict[str, Any], *keys: str) -> dict[str, Any]:
    for key in keys:
        schema = _dereferenced(document, schema)[key]
    return _dereferenced(document, schema)


def test_the_json_schema_types_med_as_a_number() -> None:
    document = json_document(ROOT, 'ExaBGP configuration')
    route = _at(document, document['$defs']['neighbor'], 'properties', 'static', 'properties', 'route', 'items')
    med = _at(document, route, 'properties', 'med')
    assert med == {
        'type': 'integer',
        'minimum': 0,
        'maximum': 4294967295,
        'description': 'MULTI_EXIT_DISC, RFC 4271 5.1.4: the lower is preferred',
    }


# its own number, not the module's: a test reading the threshold the code shares by says
# nothing when that threshold is what is wrong
JSON_REPEATED_OCTETS = 256


def _containers(node: Any, depth: int = 0) -> Iterator[dict[str, Any]]:
    """Every object schema of the document, those inside $defs included."""
    assert depth < MAX_DEPTH * 4
    if isinstance(node, dict):
        if 'properties' in node:
            yield node
        for each in node.values():
            yield from _containers(each, depth + 1)
    elif isinstance(node, list):
        for each in node:
            yield from _containers(each, depth + 1)


def test_an_identical_container_is_declared_once() -> None:
    """The route values of every announce family were repeated, and the schema was 509 KB."""
    document = json_document(ROOT, 'ExaBGP configuration')
    seen: dict[str, int] = {}
    for container in _containers(document):
        text = json.dumps(container, sort_keys=True)
        if len(text) >= JSON_REPEATED_OCTETS:
            seen[text] = seen.get(text, 0) + 1
    repeated = [text[:80] for text, count in seen.items() if count > 1]
    assert repeated == []


def test_a_shared_container_is_referenced_where_it_was_copied() -> None:
    """What was moved to $defs is used from more than one place, and every reference resolves."""
    document = json_document(ROOT, 'ExaBGP configuration')
    text = json.dumps(document)
    for name in document['$defs']:
        assert text.count(f'"#/$defs/{name}"') >= 2 or name == 'neighbor', name
    assert len(document['$defs']) > 1, 'nothing was shared, the route values are copied again'


# --------------------------------------------------------------------------- YANG

IDENTIFIER = re.compile(r'[a-zA-Z_][a-zA-Z0-9_.-]*')
BUILT_IN = frozenset(
    {'uint8', 'uint16', 'uint32', 'uint64', 'int64', 'boolean', 'empty', 'enumeration', 'string', 'union'}
)
INET = frozenset({'inet:ip-address', 'inet:ipv4-address', 'inet:ipv6-address', 'inet:ip-prefix', 'inet:as-number'})
NAMED = ('container', 'list', 'leaf', 'leaf-list', 'choice', 'case', 'grouping')


def _statements(lines: list[str]) -> Iterator[tuple[str, str]]:
    for line in lines:
        keyword, _, argument = line.strip().partition(' ')
        yield keyword, argument.rstrip(' {;')


def test_the_yang_module_is_well_formed() -> None:
    lines = yang_module(ROOT)
    # the braces of the statements, not those a description quotes
    text = re.sub(r"'[^']*'|\"(\\.|[^\"\\])*\"", '', '\n'.join(lines))
    assert text.count('{') == text.count('}')
    statements = list(_statements(lines))
    groupings = {argument for keyword, argument in statements if keyword == 'grouping'}
    for keyword, argument in statements:
        if keyword in NAMED:
            assert IDENTIFIER.fullmatch(argument), f'{keyword} {argument}'
        if keyword == 'uses':
            assert argument in groupings
        if keyword == 'type':
            assert argument in BUILT_IN or argument in INET, argument
        if keyword == 'pattern':
            re.compile(argument.strip("'"))


# its own number, not the module's: a test reading the threshold the code shares by says
# nothing when that threshold is what is wrong
YANG_REPEATED_LINES = 8


def _yang_bodies(lines: list[str]) -> Iterator[tuple[str, ...]]:
    """The body of every container and list, its lines without their indentation."""
    for start, line in enumerate(lines):
        if not line.strip().startswith(('container ', 'list ')) or not line.endswith('{'):
            continue
        indent = len(line) - len(line.lstrip())
        body: list[str] = []
        for inner in lines[start + 1 :]:
            if inner.strip() == '}' and len(inner) - len(inner.lstrip()) == indent:
                break
            body.append(inner.strip())
        yield tuple(body)


def test_an_identical_yang_container_is_a_grouping() -> None:
    """The route values of every announce family were printed again for each of them."""
    seen: dict[tuple[str, ...], int] = {}
    for body in _yang_bodies(yang_module(ROOT)):
        if len(body) >= YANG_REPEATED_LINES:
            seen[body] = seen.get(body, 0) + 1
    repeated = [body[:3] for body, count in seen.items() if count > 1]
    assert repeated == []


def test_every_yang_list_has_a_key_it_defines() -> None:
    lines = yang_module(ROOT)
    for index, line in enumerate(lines):
        if not line.strip().startswith('list '):
            continue
        body = lines[index + 1 : index + 4]
        key = next(each.strip() for each in body if each.strip().startswith('key '))
        name = key.removeprefix('key ').strip("';")
        assert any(f'leaf {name} {{' in each for each in lines[index:]), f'{line.strip()} has no leaf {name}'


def test_yang_types_med_as_uint32() -> None:
    lines = [line.strip() for line in yang_module(ROOT)]
    med = lines.index('leaf med {')
    assert 'type uint32;' in lines[med + 1 : med + 3]


# --------------------------------------------------------------------------- what the model tells


def _undescribed(value: Shape, path: str, depth: int = 0) -> Iterator[str]:
    assert depth < MAX_DEPTH
    for group in value.uses:
        yield from _undescribed(group, path, depth + 1)
    for name, each in value.fields:
        if not each.description:
            yield f'{path}/{name}'
        yield from _undescribed(each, f'{path}/{name}', depth + 1)
    if value.item is not None:
        yield from _undescribed(value.item, f'{path}[]', depth + 1)


def test_every_member_is_described() -> None:
    assert sorted(set(_undescribed(model(ROOT), ''))) == []


def test_a_default_is_a_value_of_its_model() -> None:
    wrong = [
        f'{path} default {value.default!r}'
        for path, value in _members(model(ROOT), '')
        if value.default is not None
        and value.kind not in (Kind.LIST, Kind.CONTAINER)
        and not accepts(value, value.default)
    ]
    assert wrong == []


def test_the_defaults_are_what_a_neighbor_holds() -> None:
    neighbor = dict(model(ROOT).fields)['neighbor'].item
    assert neighbor is not None
    members = dict(neighbor.uses[0].fields)
    assert members['hold-time'].default == '180'
    assert members['passive'].default == 'false'
    capability = dict(members['capability'].fields)
    assert capability['asn4'].default == 'enable'
    # a neighbor without the statement does not advertise graceful restart
    assert capability['graceful-restart'].default == 'disable'


def test_a_capability_is_a_boolean_or_required() -> None:
    document = json_document(ROOT, 'ExaBGP configuration')
    asn4 = document['$defs']['neighbor']['properties']['capability']['properties']['asn4']
    assert asn4['anyOf'] == [{'type': 'boolean'}, {'type': 'string', 'enum': ['require']}]
    assert asn4['default'] is True


def test_the_needed_statements_are_those_a_neighbor_is_refused_without() -> None:
    from exabgp.configuration.grammar.describe import needed
    from exabgp.configuration.grammar.tree.neighbor import NEIGHBOR
    from exabgp.configuration.grammar.tree.resolve import MANDATORY, TCP_AO_MANDATORY

    paths = set(needed(NEIGHBOR))
    # peer-address is the name of the neighbor block, always there
    assert {name for name in MANDATORY if name != 'peer-address'} <= paths
    assert {f'tcp-ao/{name}' for name in TCP_AO_MANDATORY} <= paths
    assert paths == {'local-as', 'peer-as', 'role/local', *(f'tcp-ao/{name}' for name in TCP_AO_MANDATORY)}


def test_a_template_needs_nothing() -> None:
    document = json_document(ROOT, 'ExaBGP configuration')
    template = document['properties']['template']['properties']['neighbor']['items']
    assert template['required'] == ['name']
    assert 'properties' not in template or all('required' not in each for each in template['properties'].values())
