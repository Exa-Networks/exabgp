"""What the grammar tells about itself covers every keyword it reads."""

from __future__ import annotations

import json

import pytest

from config_grammar.forms import declared_leaves, wrapper
from config_grammar.outcome import Rejected
from config_grammar.outcome import read_text as read_outcome
from exabgp.configuration.grammar.describe import find, json_document, locate, route_help, statement_help, syntax
from exabgp.configuration.grammar.nodes import Block, Leaf
from exabgp.configuration.grammar.shape import Kind
from exabgp.configuration.grammar.tree.root import ROOT


def _schema_at(path: tuple[str, ...]) -> dict:
    document = json_document(ROOT, 'ExaBGP configuration')
    schema = document
    for keyword in path:
        if '$ref' in str(schema.get('allOf', '')):
            schema = document['$defs'][schema['allOf'][0]['$ref'].removeprefix('#/$defs/')]
        schema = schema['properties'][keyword]
        inner = schema.get('additionalProperties')
        schema = schema.get('items', inner if isinstance(inner, dict) else schema)
    if 'allOf' in schema:
        schema = document['$defs'][schema['allOf'][0]['$ref'].removeprefix('#/$defs/')]
    return schema


def test_every_leaf_of_a_neighbor_is_in_the_syntax() -> None:
    text = '\n'.join(syntax(ROOT))
    for path, leaf in declared_leaves():
        if path[0] == 'template':
            continue  # a template neighbor refers to the neighbor
        assert f'\t{leaf.keyword}' in text or text.startswith(leaf.keyword), f'{"/".join(path)} {leaf.keyword}'


def test_a_template_neighbor_refers_to_the_neighbor() -> None:
    lines = syntax(ROOT)
    assert any(line.strip().startswith('neighbor <') and '# as neighbor' in line for line in lines)


def test_every_leaf_is_in_the_json_schema() -> None:
    for path, leaf in declared_leaves():
        if leaf.type.shape().kind == Kind.REFUSED:
            continue  # only there to be refused, it holds no data
        assert leaf.keyword in _schema_at(path)['properties'], f'{"/".join(path)} {leaf.keyword}'


def test_a_route_keyword_has_its_syntax_and_an_example() -> None:
    found = route_help('next-hop')
    assert found is not None
    assert found.hint == '<ip>|self'
    assert found.example
    assert route_help('nothing') is None


def test_a_section_is_found_by_its_keywords() -> None:
    block = find(ROOT, ['neighbor', 'family'])
    assert isinstance(block, Block) and block.keyword == 'family'
    with pytest.raises(ValueError, match='no section'):
        find(ROOT, ['neighbor', 'nothing'])


def test_the_command_prints_a_section(capsys) -> None:
    from argparse import Namespace

    from exabgp.application.syntax import cmdline

    assert cmdline(Namespace(section=['process'], json=False, yang=False)) == 0
    out = capsys.readouterr().out
    assert out.startswith('process <name> {\n')
    assert '\trun <program>' in out
    assert cmdline(Namespace(section=['nothing'], json=False, yang=False)) == 1


def test_a_statement_is_found_by_its_keywords() -> None:
    found = locate(ROOT, ['neighbor', 'hold-time'])
    assert isinstance(found, Leaf) and found.keyword == 'hold-time'
    assert isinstance(locate(ROOT, ['neighbor', 'family']), Block)
    with pytest.raises(ValueError, match="no keyword 'nothing' in neighbor"):
        locate(ROOT, ['neighbor', 'nothing'])
    with pytest.raises(ValueError, match="'hold-time' is a statement"):
        locate(ROOT, ['neighbor', 'hold-time', 'more'])


def test_the_help_of_a_statement() -> None:
    lines = statement_help(ROOT, ['neighbor', 'hold-time'])
    assert lines[0] == 'neighbor hold-time 0|<3-65535>;'
    assert '\tseconds, 0 disables the hold timer' in lines
    # the neighbor default is applied where the neighbor is made, not on the leaf
    assert '\tdefault 180' in lines
    assert any(line.startswith('\texample: hold-time ') for line in lines)


def test_the_help_of_a_route_value() -> None:
    lines = statement_help(ROOT, ['neighbor', 'static', 'route', 'next-hop'])
    assert lines[0] == 'neighbor static route next-hop <ip>|self;'
    assert '\tthe next-hop, or self for the local address' in lines
    assert '\tmay be repeated' not in lines


def test_the_help_of_a_mandatory_statement() -> None:
    lines = statement_help(ROOT, ['process', 'run'])
    assert '\tmandatory' in lines


@pytest.mark.parametrize(
    ('path', 'leaf'),
    declared_leaves(),
    ids=['/'.join([*path, leaf.keyword]) for path, leaf in declared_leaves()],
)
def test_every_statement_has_its_help(path: tuple[str, ...], leaf: Leaf) -> None:
    lines = statement_help(ROOT, [*path, leaf.keyword])
    assert lines[0].startswith(' '.join([*path, leaf.keyword]))
    assert lines[0].endswith(';')
    if leaf.doc:
        assert f'\t{leaf.doc}' in lines


def test_the_command_prints_a_statement(capsys) -> None:
    from argparse import Namespace

    from exabgp.application.syntax import cmdline

    assert cmdline(Namespace(section=['neighbor', 'hold-time'], json=False, yang=False)) == 0
    out = capsys.readouterr().out
    assert out.startswith('neighbor hold-time 0|<3-65535>;\n')
    assert cmdline(Namespace(section=['neighbor', 'hold-time'], json=True, yang=False)) == 0
    schema = json.loads(capsys.readouterr().out)
    assert schema['type'] == 'integer' and schema['default'] == 180
    assert cmdline(Namespace(section=['neighbor', 'hold-time'], json=False, yang=True)) == 1
    assert 'a section' in capsys.readouterr().err


def _given_twice(path: tuple[str, ...], leaf: Leaf) -> str | None:
    """What reading the statement twice does: 'adds', 'replaces' or 'refused', None if untold.

    Two spellings which read to different values are needed: the same one twice can not tell
    adding from replacing. Every pair is tried, a list may hold the entries of a shorter one.
    """
    document = wrapper(path, leaf.keyword)
    accepted: list[tuple[str, object]] = []
    for example in leaf.type.examples():
        statement = f'{leaf.keyword} {example}'.rstrip()
        found, _ = read_outcome(document.format(form=statement))
        if not isinstance(found, Rejected) and all(found != each for _, each in accepted):
            accepted.append((statement, found))
    if len(accepted) < 2:
        return None
    told = set()
    for first, first_outcome in accepted:
        for second, second_outcome in accepted:
            if first == second:
                continue
            both, _ = read_outcome(document.format(form=f'{first}; {second}'))
            if isinstance(both, Rejected):
                told.add('refused')
            elif both in (first_outcome, second_outcome):
                told.add('replaces')
            else:
                return 'adds'
    return 'refused' if told == {'refused'} else 'replaces'


@pytest.mark.parametrize(
    ('path', 'leaf'),
    [(path, leaf) for path, leaf in declared_leaves() if path[:1] != ('template',)],
    ids=['/'.join([*path, leaf.keyword]) for path, leaf in declared_leaves() if path[:1] != ('template',)],
)
def test_may_be_repeated_is_said_of_a_statement_which_adds(path: tuple[str, ...], leaf: Leaf) -> None:
    told = _given_twice(path, leaf)
    if told is None:
        pytest.skip('fewer than two spellings read to different values')
    said = '\tmay be repeated' in statement_help(ROOT, [*path, leaf.keyword])
    assert said == (told == 'adds'), f'given twice, the statement {told}'


def test_the_repetition_check_can_fail() -> None:
    # a statement whose second value replaces the first, and one whose values add up
    assert _given_twice(('neighbor',), ROOT.block('neighbor').leaf('hold-time')) == 'replaces'
    route = find(ROOT, ['neighbor', 'static', 'route'])
    assert _given_twice(('neighbor', 'static', 'route'), route.leaf('community')) == 'adds'
    assert _given_twice(('neighbor', 'static', 'route'), route.leaf('med')) == 'refused'
