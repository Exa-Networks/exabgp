"""`exabgp configuration example`: a documented neighbor, generated from the grammar.

The example gives the four statements a neighbor must have and every other statement and
section commented out with its description, so the file is read as it is and documents
every keyword of the neighbor block.
"""

from __future__ import annotations

from argparse import Namespace
from pathlib import Path
from typing import Iterator

import pytest

from exabgp.application.example import cmdline
from exabgp.configuration.configuration import Configuration
from exabgp.configuration.grammar.example import GIVEN, INDENT, example
from exabgp.configuration.grammar.nodes import Block, Leaf
from exabgp.configuration.grammar.shape import Kind
from exabgp.configuration.grammar.tree.neighbor import NEIGHBOR

MAX_DEPTH = 40


def _documented(block: Block, depth: int = 1) -> Iterator[tuple[str, Leaf | Block]]:
    """Each statement and section of the block, with the indentation the example writes it at."""
    assert depth < MAX_DEPTH
    for child in block.children:
        if isinstance(child, Leaf) and child.type.shape().kind == Kind.REFUSED:
            continue
        yield INDENT * depth, child
        if isinstance(child, Block):
            yield from _documented(child, depth + 1)


def test_the_example_is_a_configuration(tmp_path: Path) -> None:
    path = tmp_path / 'example.conf'
    path.write_text(example())
    configuration = Configuration([str(path)])
    assert configuration.reload() is True, configuration.error


def test_the_example_documents_every_keyword_of_a_neighbor() -> None:
    lines = example().splitlines()
    missing = []
    for indent, child in _documented(NEIGHBOR):
        described = f'{indent}# {child.keyword}: {child.doc}' if child.doc else f'{indent}# {child.keyword}'
        if described not in lines:
            missing.append(described.strip())
    assert missing == []


def test_the_example_gives_a_type_for_every_statement() -> None:
    text = example()
    missing = [
        child.keyword
        for indent, child in _documented(NEIGHBOR)
        if isinstance(child, Leaf) and child.type.hint() and f'{indent}# Type: {child.type.hint()}' not in text
    ]
    assert missing == []


@pytest.mark.parametrize('keyword', sorted(GIVEN))
def test_the_mandatory_statements_are_given(keyword: str) -> None:
    lines = example().splitlines()
    assert f'{INDENT}{keyword} {GIVEN[keyword]};' in lines
    assert f'{INDENT}# {keyword} {GIVEN[keyword]};' not in lines


def test_every_other_statement_is_commented_out() -> None:
    body = example().split('neighbor 127.0.0.1 {', 1)[1].splitlines()
    given = [line.strip() for line in body if line.strip() and not line.strip().startswith('#')]
    assert given == [f'{keyword} {value};' for keyword, value in GIVEN.items()] + ['}']


def test_the_example_shows_the_default_hold_time() -> None:
    lines = example().splitlines()
    leaf = NEIGHBOR.leaf('hold-time')
    assert leaf is not None
    hold_time = lines.index(f'{INDENT}# hold-time: {leaf.doc}')
    assert f'{INDENT}# Default: 180' in lines[hold_time : hold_time + 4]
    assert f'{INDENT}# hold-time 180;' in lines[hold_time : hold_time + 5]


def test_the_command_writes_the_example(capsys: pytest.CaptureFixture[str]) -> None:
    assert cmdline(Namespace(section=None)) == 0
    assert capsys.readouterr().out == example()
