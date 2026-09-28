"""A configuration error names the line the statement is on.

It named the count of statements read so far, so blank lines, comments and several
statements on one line all moved the reported line away from the real one: an error on
line 7 was reported on line 6.

The grammar names it with the column, and the file when there is one:
`broken.conf:7:10: 'jsn' is not a valid encoder`.
"""

from __future__ import annotations

import pytest

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


def error_of(configuration: Configuration) -> str:
    assert not configuration.reload()
    return str(configuration.error)


def named(line: int, column: int, where: str = 'line ') -> str:
    """How the `encoder jsn` statement on `line` is named, `where` being the file or `line `."""
    return f"{where}{line}:{column}: 'jsn' is not a valid encoder"


def test_the_error_names_the_line_of_the_statement_in_text() -> None:
    assert named(7, 10) in error_of(Configuration([TEXT], text=True))


def test_the_error_names_the_line_of_the_statement_in_a_file(tmp_path) -> None:
    path = tmp_path / 'broken.conf'
    path.write_text(TEXT)

    assert named(7, 10, f'{path}:') in error_of(Configuration([str(path)]))


def test_a_continuation_line_does_not_shift_the_lines_after_it(tmp_path) -> None:
    path = tmp_path / 'continued.conf'
    path.write_text(TEXT.replace('\trun /bin/cat;', '\trun /bin/cat \\\n\t\t--flag;'))

    assert named(8, 10, f'{path}:') in error_of(Configuration([str(path)]))


@pytest.mark.parametrize('line', [1, 3])
def test_the_first_statement_of_a_line_is_the_one_named(line: int) -> None:
    text = '\n' * (line - 1) + 'process p { run /bin/cat; encoder jsn; }\n'

    assert named(line, 35) in error_of(Configuration([text], text=True))
