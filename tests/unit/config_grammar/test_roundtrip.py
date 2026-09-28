"""What the grammar prints reads back to the same configuration, with either parser."""

from __future__ import annotations

import os
from typing import Any

import pytest

from config_grammar.differential import Accepted, agree, grammar, grammar_file, legacy
from config_grammar.forms import DOCUMENTS, all_forms
from config_grammar.test_differential import CONFIGURATIONS, ROOT as REPOSITORY
from exabgp.configuration.grammar.read import read_file, read_text
from exabgp.configuration.grammar.render import quote, render
from exabgp.configuration.grammar.tree.root import ROOT
from exabgp.configuration.grammar.tree.static import Unprintable

VALID = [form.document() for form in all_forms() if form.valid] + [text for text, valid in DOCUMENTS if valid]


def _unordered(outcome: Any) -> Any:
    """The outcome with the routes of each neighbor in a set order."""
    if not isinstance(outcome, Accepted):
        return outcome
    neighbors = {}
    for name, state in outcome.neighbors.items():
        neighbors[name] = {**state, 'routes': sorted(state['routes'], key=repr)}
    return Accepted(processes=outcome.processes, neighbors=neighbors)


def _printed(document: str) -> str:
    try:
        return render(ROOT, read_text(document))
    except Unprintable as exc:
        # a route no statement writes: an IPv6 prefix in an IPv4 family, shown by nothing either
        pytest.skip(str(exc))


@pytest.mark.parametrize('document', VALID)
def test_printed_configuration_reads_back_equal(document: str) -> None:
    printed = _printed(document)

    # compared on what the configuration makes: Settings holding a route with `next-hop self`
    # can not be compared, NextHopSelf refuses __eq__. The routes are printed section by
    # section, static, announce, flow, so their order across sections is not kept
    assert agree(_unordered(grammar(printed)), _unordered(grammar(document))), printed
    assert render(ROOT, read_text(printed)) == printed, 'printing is not stable'


@pytest.mark.parametrize('document', VALID)
def test_printed_configuration_reads_the_same_with_the_legacy_parser(document: str) -> None:
    printed = _printed(document)
    old = legacy(printed)

    assert isinstance(old, Accepted), f'the legacy parser refuses what the grammar printed:\n{printed}\n{old}'
    assert agree(_unordered(old), _unordered(grammar(document)))


@pytest.mark.parametrize('path', CONFIGURATIONS, ids=lambda path: os.path.relpath(path, REPOSITORY))
def test_a_printed_configuration_file_reads_back_equal(path: str) -> None:
    original = grammar_file(path)
    if not isinstance(original, Accepted):
        pytest.skip('a configuration both parsers refuse')
    try:
        printed = render(ROOT, read_file(path))
    except Unprintable as exc:
        pytest.skip(str(exc))

    assert agree(_unordered(grammar(printed)), _unordered(original)), printed
    old = legacy(printed)
    assert isinstance(old, Accepted), f'the legacy parser refuses what the grammar printed:\n{printed}\n{old}'
    assert agree(_unordered(old), _unordered(original)), printed


@pytest.mark.parametrize(
    'word', ['plain', '', 'with space', 'semi;colon', 'brace{', '#hash', 'back\\slash', 'tab\there', '[', ',']
)
def test_a_quoted_word_lexes_back_to_itself(word: str) -> None:
    from exabgp.configuration.grammar.lexer import lex_text

    statement = lex_text(f'keyword {quote(word)};')[0]
    assert [token.word for token in statement.words] == ['keyword', word]


@pytest.mark.parametrize('word', ['it"s', "it's"])
def test_a_word_with_a_quote_can_not_be_printed(word: str) -> None:
    with pytest.raises(ValueError):
        quote(word)


def test_the_round_trip_can_fail() -> None:
    settings = read_text('process p { run /bin/cat; respawn false; }')
    other = read_text('process p { run /bin/cat; }')
    assert settings != other
