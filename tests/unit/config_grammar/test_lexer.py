"""The grammar lexer splits text into the words the legacy tokeniser did, and knows where each came from.

The expected words were those of the legacy tokeniser (configuration/core/format.py), which
the lexer was compared with until it was removed.
"""

from __future__ import annotations

import glob
import os

import pytest

from exabgp.configuration.grammar.error import ConfigError
from exabgp.configuration.grammar.lexer import lex_file, lex_text

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
CONFIGURATIONS = sorted(glob.glob(os.path.join(ROOT, 'etc', 'exabgp', '*.conf')))

TRICKY: list[tuple[str, list[list[str]] | str]] = [
    ('a b;', [['a', 'b', ';']]),
    ('a "b c" d;', [['a', 'b c', 'd', ';']]),
    ("a 'b \"c' d;", 'rejected'),
    ('a "" b;', [['a', '', 'b', ';']]),
    ('ab"cd" e;', [['abcd', 'e', ';']]),
    ('a "b\'c" d;', 'rejected'),
    ('a [ 1 2 ];', [['a', '[', '1', '2', ']', ';']]),
    ('a [1,2];', [['a', '[', '1', ',', '2', ']', ';']]),
    ('a(1) b;', [['a(1)', 'b', ';']]),
    ('a { b; } c;', [['a', '{'], ['b', ';'], ['}'], ['c', ';']]),
    ('a;#comment', [['a', ';']]),
    ('# comment', []),
    ('   ', []),
    ('', []),
    ('a "#" b;', [['a', '#', 'b', ';']]),
    ('a \\u0041 b;', [['a', 'A', 'b', ';']]),
    ('a \\n b;', [['a', 'b', ';']]),
    ('a \\;', [['a', ';']]),
    ('a "b;c" d;', [['a', 'b;c', 'd', ';']]),
    ('\ta\tb ;', [['a', 'b', ';']]),
    ('a b', 'rejected'),
    ('a # b;', 'rejected'),
    ('a b# c;', 'rejected'),
    ('a "b', 'rejected'),
    ('a \\u12;', 'rejected'),
    ('a \\uzzzz;', 'rejected'),
    ('}', [['}']]),
    (';', [[';']]),
]


def grammar_words(text: str) -> list[list[str]] | str:
    try:
        return [[token.word for token in statement.tokens] for statement in lex_text(text)]
    except ConfigError:
        return 'rejected'


@pytest.mark.parametrize('text,words', TRICKY)
def test_tricky_lines_split_as_the_legacy_tokeniser_split_them(text: str, words: list[list[str]] | str) -> None:
    assert grammar_words(text) == words


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
    path = tmp_path / 'continued.conf'
    path.write_text('process p {\n\trun /bin/cat \\\n\t\t--flag;\n\tencoder json;\n}\n')
    # the statements the legacy parser read from the file
    legacy = [['process', 'p', '{'], ['run', '/bin/cat', '--flag', ';'], ['encoder', 'json', ';'], ['}']]

    statements = lex_file(str(path))
    assert [[token.word for token in statement.tokens] for statement in statements] == legacy
    encoder = statements[2].tokens[0]
    assert (encoder.word, encoder.line) == ('encoder', 4), 'a continuation shifted the lines after it'
    flag = statements[1].tokens[2]
    assert (flag.word, flag.line) == ('--flag', 3), 'a word on a continuation line reports its own line'
