"""test_md5_base64.py

md5-base64 selects how md5-password is read, and it has to be an explicit
choice.  Guessing base64 from the shape of the password installs a different
key whenever the password happens to be hexadecimal, which is exactly what
`openssl rand -hex` produces (#1423).

Copyright (c) 2009-2026 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from exabgp.configuration.configuration import Configuration
from exabgp.util.psk import guessed_as_base64

# A key an operator would get from `openssl rand -hex 16`: every character is
# in the base64 alphabet and the length is a multiple of four, so it decodes
# cleanly into a different key without any error to warn about it.
HEX_PASSWORD = '3f9a1c2b7d4e8f0a1b2c3d4e5f607182'

NEIGHBOR = """\
neighbor 192.0.2.1 {
    router-id 10.0.0.1;
    local-address 192.0.2.2;
    local-as 65000;
    peer-as 65001;
    md5-password "%s";
%s}
"""


def _parse(tmp_path, password: str, extra: str = '') -> Configuration:
    configuration = tmp_path / 'md5.conf'
    configuration.write_text(NEIGHBOR % (password, extra))
    return Configuration([str(configuration)])


def test_md5_base64_defaults_to_the_password_being_literal(tmp_path) -> None:
    configuration = _parse(tmp_path, HEX_PASSWORD)

    assert configuration.reload(), str(configuration.error)

    (neighbor,) = configuration.neighbors.values()
    assert neighbor.session.md5_base64 is False
    assert neighbor.session.md5_password == HEX_PASSWORD


@pytest.mark.parametrize(
    'value,expected',
    [
        ('true', True),
        ('enable', True),
        ('false', False),
        ('disable', False),
    ],
)
def test_md5_base64_is_an_explicit_choice(tmp_path, value: str, expected: bool) -> None:
    configuration = _parse(tmp_path, HEX_PASSWORD, f'    md5-base64 {value};\n')

    assert configuration.reload(), str(configuration.error)

    (neighbor,) = configuration.neighbors.values()
    assert neighbor.session.md5_base64 is expected


def test_md5_base64_auto_explains_its_removal(tmp_path) -> None:
    """'auto' guessed base64 from the password content, so it no longer exists (#1423).

    Whoever wrote it knew about the guess, so the error has to say it is gone and
    which value replaces it, not just that 'auto' is not a boolean.
    """
    configuration = _parse(tmp_path, HEX_PASSWORD, '    md5-base64 auto;\n')

    assert not configuration.reload()

    error = str(configuration.error)
    assert 'md5-base64 true;' in error
    assert 'md5-base64 false;' in error


def _warnings(configuration: Configuration) -> list[str]:
    """Return the configuration warnings raised while parsing."""
    with patch('exabgp.configuration.neighbor.log') as log:
        assert configuration.reload(), str(configuration.error)
    return [call.args[0]() for call in log.warning.call_args_list]


def test_an_upgrade_which_changes_the_key_is_reported(tmp_path) -> None:
    """Up to 4.2 this password was decoded, so the key on the wire changes on upgrade (#1423)."""
    (warning,) = _warnings(_parse(tmp_path, HEX_PASSWORD))

    assert '192.0.2.1' in warning
    # both ways out are named: keep the old key, or confirm the password and be quiet
    assert 'md5-base64 true;' in warning
    assert 'md5-base64 false;' in warning


@pytest.mark.parametrize('choice', ['true', 'false'])
def test_an_explicit_choice_is_not_second_guessed(tmp_path, choice: str) -> None:
    """The operator has said how to read the password, so there is nothing to report."""
    assert _warnings(_parse(tmp_path, HEX_PASSWORD, f'    md5-base64 {choice};\n')) == []


@pytest.mark.parametrize('password', ['secret', '3F9A1C2B7D4E8F0A', 'abcdef123'])
def test_a_password_the_guess_never_touched_is_not_reported(tmp_path, password: str) -> None:
    """Not hex, uppercase hex, or hex of a length base64 rejects: none were ever decoded."""
    assert _warnings(_parse(tmp_path, password)) == []


@pytest.mark.parametrize(
    'password,guessed',
    [
        ('3f9a1c2b7d4e8f0a1b2c3d4e5f607182', True),  # openssl rand -hex 16
        ('abcdef1234', True),  # ten hex characters, decoded once padded
        ('abcdef123', False),  # nine, no amount of padding makes it base64
        ('3F9A1C2B7D4E8F0A', False),  # the guess only ever matched lowercase
        ('secret', False),
        ('', False),
    ],
)
def test_guessed_as_base64_repeats_the_removed_heuristic(password: str, guessed: bool) -> None:
    assert guessed_as_base64(password) is guessed
