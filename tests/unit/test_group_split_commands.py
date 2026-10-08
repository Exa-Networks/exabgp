"""A `group` line ends a command at a `;` the lexer ends a statement with, and nowhere else.

It was split on every `;`, so a word in quotes holding one was cut in two, and what followed
it read as a command of its own: a name a peer chose for its SR policy, printed by
`exabgp decode --command`, could withdraw routes once the group was sent.
"""

from __future__ import annotations

import pytest

from exabgp.configuration.grammar.lexer import split_commands


@pytest.mark.parametrize(
    ('line', 'commands'),
    [
        ('announce route 10.0.0.0/24 next-hop 1.1.1.1', ['announce route 10.0.0.0/24 next-hop 1.1.1.1']),
        ('announce a ; withdraw b ;', ['announce a', 'withdraw b']),
        # in quotes, either quote character
        (
            'announce a policy-name "x ; withdraw b ; y" ; announce c',
            ['announce a policy-name "x ; withdraw b ; y"', 'announce c'],
        ),
        ("announce a name 'x ; y' ; announce c", ["announce a name 'x ; y'", 'announce c']),
        # one quote character inside the other is a character
        ('announce a name "x \' ; y" ; announce c', ['announce a name "x \' ; y"', 'announce c']),
        # the statements of a block
        (
            'announce flow route { match { destination 10.0.0.0/24; } then { discard; } } ; announce c',
            ['announce flow route { match { destination 10.0.0.0/24; } then { discard; } }', 'announce c'],
        ),
        # the lexer resolves escapes first: an escaped quote opens a quote, an escaped `;` ends a command
        ('announce a \\" ; b \\" ; announce c', ['announce a \\" ; b \\"', 'announce c']),
        ('announce a \\u0022 ; b \\u0022 ; announce c', ['announce a \\u0022 ; b \\u0022', 'announce c']),
        ('announce a \; announce c', ['announce a', 'announce c']),
    ],
)
def test_a_group_is_split_where_the_lexer_ends_a_statement(line: str, commands: list[str]) -> None:
    assert split_commands(line) == commands
