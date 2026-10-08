"""A statement refused when given twice is named by a keyword the user can find.

The message named the attribute by a table of keywords which left out the internal ones, so
`split /25 split /26` was refused as `attribute 0xfffd is given twice`, a code no statement
spells. The name may be another statement of the same block: `attribute [ 0x20 ... ]` is a
large-community, `bgp-prefix-sid-srv6` a bgp-prefix-sid, and those are said. In a block without
that statement (vpls has no large-community) the attribute is named by its route keyword.
"""

from __future__ import annotations

import re

import pytest

from config_grammar.forms import declared_leaves, wrapper
from config_grammar.outcome import Rejected, read_text
from exabgp.configuration.grammar.describe import locate
from exabgp.configuration.grammar.nodes import Block, Leaf
from exabgp.configuration.grammar.tree.root import ROOT
from exabgp.configuration.grammar.tree.static import ROUTE_VALUES

TWICE = re.compile(r'(\S+) is given twice, it can be given once')


def _refused_twice(path: tuple[str, ...], leaf: Leaf) -> str | None:
    """The name the message gives a statement refused twice, None if it is not refused."""
    document = wrapper(path, leaf.keyword)
    for example in leaf.type.examples():
        statement = f'{leaf.keyword} {example}'.rstrip()
        once, _ = read_text(document.format(form=statement))
        if isinstance(once, Rejected):
            continue
        twice, _ = read_text(document.format(form=f'{statement}; {statement}'))
        found = TWICE.search(twice.message) if isinstance(twice, Rejected) else None
        return found.group(1) if found else None
    return None


@pytest.mark.parametrize(
    ('path', 'leaf'),
    [(path, leaf) for path, leaf in declared_leaves() if path[0] != 'template'],
    ids=['/'.join([*path, leaf.keyword]) for path, leaf in declared_leaves() if path[0] != 'template'],
)
def test_a_statement_given_twice_is_named_by_a_keyword(path: tuple[str, ...], leaf: Leaf) -> None:
    name = _refused_twice(path, leaf)
    if name is None:
        pytest.skip('not refused when given twice')
    block = locate(ROOT, list(path))
    assert isinstance(block, Block)
    assert block.leaf(name) is not None or name in ROUTE_VALUES, f'given twice, {leaf.keyword} is called {name}'


@pytest.mark.parametrize('keyword', ['split', 'withdraw'])
def test_an_internal_attribute_is_named_by_its_keyword(keyword: str) -> None:
    route = locate(ROOT, ['neighbor', 'static', 'route'])
    assert isinstance(route, Block)
    leaf = route.leaf(keyword)
    assert leaf is not None
    assert _refused_twice(('neighbor', 'static', 'route'), leaf) == keyword
