"""What the grammar tells about itself covers every keyword it reads."""

from __future__ import annotations

import pytest

from config_grammar.forms import declared_leaves
from exabgp.configuration.grammar.describe import find, json_schema, route_help, syntax
from exabgp.configuration.grammar.nodes import Block
from exabgp.configuration.grammar.tree.root import ROOT


def _schema_at(path: tuple[str, ...]) -> dict:
    schema = json_schema(ROOT)
    for keyword in path:
        schema = schema['properties'][keyword]
        schema = schema.get('items', schema.get('additionalProperties', schema))
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

    assert cmdline(Namespace(section=['process'], json=False)) == 0
    out = capsys.readouterr().out
    assert out.startswith('process <name> {\n')
    assert '\trun <program>' in out
    assert cmdline(Namespace(section=['nothing'], json=False)) == 1
