"""A configuration error names the line the statement is on.

It named the count of statements read so far, so blank lines, comments and several
statements on one line all moved the reported line away from the real one: an error on
line 7 was reported on line 6.

Each parser names it its own way: the legacy one with the statement, `line 7: encoder jsn`,
the grammar with the column and the file, `broken.conf:7:10: 'jsn' is not a valid encoder`.
"""

from __future__ import annotations

import pytest

from exabgp.configuration.compare import GRAMMAR, LEGACY
from exabgp.configuration.configuration import Configuration

TEXT = """\
process p {
\trun /bin/cat;

\t# a comment
\tencoder text; respawn true;
\trespawn true;
\tencoder jsn;
}
"""


PARSERS = [LEGACY, GRAMMAR]


def error_of(configuration: Configuration, parser: str) -> str:
    assert not configuration.reload(parser)
    return str(configuration.error)


def named(parser: str, line: int, column: int, where: str = 'line ') -> str:
    """How `parser` names the `encoder jsn` statement on `line`, `where` being the grammar's prefix."""
    if parser == LEGACY:
        return f'line {line}: encoder jsn'
    return f"{where}{line}:{column}: 'jsn' is not a valid encoder"


@pytest.mark.parametrize('parser', PARSERS)
def test_the_error_names_the_line_of_the_statement_in_text(parser: str) -> None:
    assert named(parser, 7, 10) in error_of(Configuration([TEXT], text=True), parser)


@pytest.mark.parametrize('parser', PARSERS)
def test_the_error_names_the_line_of_the_statement_in_a_file(tmp_path, parser: str) -> None:
    path = tmp_path / 'broken.conf'
    path.write_text(TEXT)

    assert named(parser, 7, 10, f'{path}:') in error_of(Configuration([str(path)]), parser)


@pytest.mark.parametrize('parser', PARSERS)
def test_a_continuation_line_does_not_shift_the_lines_after_it(tmp_path, parser: str) -> None:
    path = tmp_path / 'continued.conf'
    path.write_text(TEXT.replace('\trun /bin/cat;', '\trun /bin/cat \\\n\t\t--flag;'))

    assert named(parser, 8, 10, f'{path}:') in error_of(Configuration([str(path)]), parser)


@pytest.mark.parametrize('parser', PARSERS)
@pytest.mark.parametrize('line', [1, 3])
def test_the_first_statement_of_a_line_is_the_one_named(line: int, parser: str) -> None:
    text = '\n' * (line - 1) + 'process p { run /bin/cat; encoder jsn; }\n'

    assert named(parser, line, 35) in error_of(Configuration([text], text=True), parser)
