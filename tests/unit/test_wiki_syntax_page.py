"""The wiki syntax reference is the grammar's own syntax, every section of it."""

from __future__ import annotations

import os
import runpy
from typing import Any

from exabgp.configuration.grammar.describe import syntax
from exabgp.configuration.grammar.render import INDENT
from exabgp.configuration.grammar.tree.root import ROOT

SCRIPT = os.path.join(os.path.dirname(__file__), '..', '..', 'qa', 'bin', 'update_wiki_syntax')


def generator() -> dict[str, Any]:
    return runpy.run_path(SCRIPT, run_name='update_wiki_syntax')


def test_every_top_level_section_has_its_heading() -> None:
    page = generator()['page']()
    for line in syntax(ROOT):
        if not line.startswith(INDENT) and line != '}':
            assert f'\n## {line.split(" ", 1)[0]}\n' in page


def test_every_statement_of_the_grammar_is_on_the_page() -> None:
    page = generator()['page']()
    for line in syntax(ROOT):
        assert line.strip() in page, line


def test_the_page_is_fenced_so_no_markdown_is_read_from_the_syntax() -> None:
    page = generator()['page']()
    assert page.count('```text') == len(generator()['sections']())
    assert '\t' not in page
