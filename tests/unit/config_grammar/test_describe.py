"""What the grammar tells about itself covers every keyword it reads."""

from __future__ import annotations

import pytest

from config_grammar.forms import declared_leaves
from exabgp.configuration.grammar.describe import find, json_document, route_help, syntax
from exabgp.configuration.grammar.nodes import Block
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
