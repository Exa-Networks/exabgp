"""Two unhandled cases in the configuration text handling, one of which corrupted quietly.

unescape() read the character after each backslash without checking there was one, so a
string ending in a backslash raised IndexError out of a helper whose callers only expect
the configuration ValueError.

The unicode escape was worse than a crash.  It sliced four characters and passed whatever
it got to int(), so "\\u12" at the end of a string quietly became chr(0x12): a wrong
character in the operator's configuration, reported as success.  A refused configuration
is recoverable, a silently different one is not.

Parser.__call__ had the same shape as the first: it took line[-1] from a list it may have
just emptied.  The file readers reject an empty configuration before the parser is built,
so no production path reaches it, but it is one bare index away from the same defect.
"""

from __future__ import annotations

import pytest

from exabgp.configuration.core.error import Error
from exabgp.configuration.core.format import unescape
from exabgp.configuration.core.parser import Parser
from exabgp.configuration.core.scope import Scope

MAX_LINES_READ = 5


@pytest.mark.parametrize(
    'text, expected',
    [
        ('plain', 'plain'),
        ('a\\nb', 'a\nb'),
        ('a\\tb', 'a\tb'),
        ('a\\\\b', 'a\\b'),
        ('a\\qb', 'aqb'),
        ('x\\u0041y', 'xAy'),
    ],
    ids=['plain', 'newline', 'tab', 'backslash', 'unknown escape', 'unicode'],
)
def test_the_escapes_which_worked_still_work(text: str, expected: str) -> None:
    """The guards must not have changed what a working configuration already means."""
    assert unescape(text) == expected


@pytest.mark.parametrize('text', ['\\', 'a\\', 'a\\nb\\', '\\\\\\'], ids=['alone', 'trailing', 'after one', 'odd run'])
def test_a_backslash_which_escapes_nothing_is_not_a_crash(text: str) -> None:
    """It yields the backslash, which is what an unknown escape already did."""
    assert unescape(text).endswith('\\'), 'the trailing backslash was lost'


@pytest.mark.parametrize(
    'text', ['x\\u12', 'x\\u', 'x\\u1', 'x\\u123'], ids=['two digits', 'none', 'one digit', 'three digits']
)
def test_a_truncated_unicode_escape_is_refused_rather_than_guessed(text: str) -> None:
    """chr(0x12) for "\\u12" was a wrong character reported as a correct configuration."""
    with pytest.raises(ValueError, match='hexadecimal digits'):
        unescape(text)


@pytest.mark.parametrize('text', ['x\\uzzzz', 'x\\u12g4', 'x\\u    '], ids=['letters', 'one bad digit', 'spaces'])
def test_a_unicode_escape_which_is_not_hexadecimal_says_so(text: str) -> None:
    """int() reported "invalid literal for int() with base 16", which names nothing."""
    with pytest.raises(ValueError, match='not hexadecimal'):
        unescape(text)


@pytest.mark.parametrize('text', ['', ' ', '\t', '\n', '   \n\t\n'], ids=['empty', 'space', 'tab', 'newline', 'blank'])
def test_a_configuration_with_no_tokens_does_not_index_an_empty_line(text: str) -> None:
    """Reached by calling the parser directly; the CLI refuses these files earlier.

    ValueError is the configuration layer's own error channel, caught by section.py and
    reported as "is not a valid config file".  An IndexError is not.
    """
    parser = Parser(Scope(), Error())

    try:
        parser.set_text(text)
        for _ in range(MAX_LINES_READ):
            if not parser():
                break
    except ValueError:
        return
