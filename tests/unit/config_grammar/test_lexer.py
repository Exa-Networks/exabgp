"""The grammar lexer splits text into the words the legacy tokeniser does, and knows where each came from."""

from __future__ import annotations

import glob
import os

import pytest

from exabgp.configuration.core.format import tokens
from exabgp.configuration.grammar.error import ConfigError
from exabgp.configuration.grammar.lexer import lex_file, lex_text

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
CONFIGURATIONS = sorted(glob.glob(os.path.join(ROOT, 'etc', 'exabgp', '*.conf')))

TRICKY = [
    'a b;',
    'a "b c" d;',
    "a 'b \"c' d;",
    'a "" b;',
    'ab"cd" e;',
    'a "b\'c" d;',
    'a [ 1 2 ];',
    'a [1,2];',
    'a(1) b;',
    'a { b; } c;',
    'a;#comment',
    '# comment',
    '   ',
    '',
    'a "#" b;',
    'a \\u0041 b;',
    'a \\n b;',
    'a \\;',
    'a "b;c" d;',
    '\ta\tb ;',
    'a b',
    'a # b;',
    'a b# c;',
    'a "b',
    'a \\u12;',
    'a \\uzzzz;',
    '}',
    ';',
]


def legacy_words(text: str) -> list[list[str]] | str:
    try:
        return [[word for _, _, word in statement] for statement in tokens(text.split('\n'))]
    except ValueError:
        return 'rejected'


def grammar_words(text: str) -> list[list[str]] | str:
    try:
        return [[token.word for token in statement.tokens] for statement in lex_text(text)]
    except ConfigError:
        return 'rejected'


@pytest.mark.parametrize('text', TRICKY)
def test_tricky_lines_split_as_the_legacy_tokeniser_splits_them(text: str) -> None:
    assert grammar_words(text) == legacy_words(text)


@pytest.mark.parametrize('path', CONFIGURATIONS, ids=os.path.basename)
def test_every_example_configuration_splits_as_the_legacy_tokeniser_splits_it(path: str) -> None:
    with open(path) as handle:
        text = handle.read()
    if '\\\n' in text:
        pytest.skip('a continuation line is joined by the file reader, compared in test_continuation')
    assert grammar_words(text) == legacy_words(text)


def test_the_example_configurations_were_found() -> None:
    assert len(CONFIGURATIONS) > 100


def test_positions_are_physical_lines_and_columns() -> None:
    statements = lex_text('\n\n  process p {\n\trun /bin/cat;\n}\n')
    first = statements[0].tokens
    assert [(token.word, token.line, token.column) for token in first] == [
        ('process', 3, 3),
        ('p', 3, 11),
        ('{', 3, 13),
    ]
    run = statements[1].tokens[0]
    assert (run.word, run.line, run.column) == ('run', 4, 2)


def test_continuation(tmp_path) -> None:
    from exabgp.configuration.core import Error, Parser, Scope

    path = tmp_path / 'continued.conf'
    path.write_text('process p {\n\trun /bin/cat \\\n\t\t--flag;\n\tencoder json;\n}\n')

    parser = Parser(Scope(), Error())
    parser.set_file(str(path))
    legacy = []
    for _ in range(10):
        line = parser()
        if not line:
            break
        legacy.append(list(line))

    statements = lex_file(str(path))
    assert [[token.word for token in statement.tokens] for statement in statements] == legacy
    encoder = statements[2].tokens[0]
    assert (encoder.word, encoder.line) == ('encoder', 4), 'a continuation shifted the lines after it'
    flag = statements[1].tokens[2]
    assert (flag.word, flag.line) == ('--flag', 3), 'a word on a continuation line reports its own line'
