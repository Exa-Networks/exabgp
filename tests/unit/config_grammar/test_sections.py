"""The tree uses its section and store implementations and names printable settings fields."""

from __future__ import annotations

import dataclasses
from typing import Iterator

from exabgp.configuration.grammar.nodes import Block, Leaf
from exabgp.configuration.grammar.read import _command_sections
from exabgp.configuration.grammar.section import Section, Store
from exabgp.configuration.grammar.tree.root import ROOT

MAX_DEPTH = 32  # as the engine: sections nest a handful deep
GRAMMAR = 'exabgp.configuration.grammar.'
ABSTRACT_SECTIONS = frozenset({'Collector'})


def _nodes(block: Block, depth: int = 0) -> Iterator[Block | Leaf]:
    assert depth <= MAX_DEPTH
    yield block
    for child in block.children:
        if isinstance(child, Block):
            yield from _nodes(child, depth + 1)
        else:
            yield child


def every_node() -> list[Block | Leaf]:
    return [node for root in (ROOT, *_command_sections().values()) for node in _nodes(root)]


def _subclasses(base: type) -> set[type]:
    found: set[type] = set()
    pending = [base]
    while pending:  # bounded: a class hierarchy has no cycle
        for each in pending.pop().__subclasses__():
            if each not in found:
                found.add(each)
                pending.append(each)
    return found


def _concrete(base: type) -> set[type]:
    return {each for each in _subclasses(base) if each.__module__.startswith(GRAMMAR)}


def test_every_section_is_used_by_a_block() -> None:
    used = {type(node.section) for node in every_node() if isinstance(node, Block)}
    # an abstract section is a base to derive from, not an implementation left behind. Named
    # rather than found with inspect.isabstract, which a class compiled by mypyc answers False
    implementations = {each for each in _concrete(Section) if each.__name__ not in ABSTRACT_SECTIONS}
    assert {each.__name__ for each in implementations - used} == set()


def test_every_store_is_used_by_a_leaf() -> None:
    used = {type(node.store) for node in every_node() if isinstance(node, Leaf) and node.store is not None}
    assert {each.__name__ for each in _concrete(Store) - used} == set()


def test_a_settings_block_prints_each_leaf_from_a_field_of_what_it_builds() -> None:
    """The printer takes a leaf's value from the field it names: one missing is never printed."""
    blocks = [node for node in every_node() if isinstance(node, Block) and node.section.builds is not None]
    assert blocks, 'no section says what Settings it builds: the test checks nothing'
    for block in blocks:
        built = block.section.builds
        assert dataclasses.is_dataclass(built), f'{block.keyword}: {built} is not a Settings dataclass'
        names = {each.name for each in dataclasses.fields(built)}
        for leaf in block.leaves():
            assert leaf.field in names, f'{block.keyword} {leaf.keyword}: {built.__name__} has no {leaf.field}'
