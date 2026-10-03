"""The completion scripts offer the subcommands `exabgp` accepts, and no other.

The scripts were written by hand when `validate` was a subcommand. It became
`exabgp configuration validate`, `configuration`, `migrate` and `schema` were added, and every
script kept offering the old list: `exabgp validate` completed, then was read as a
configuration file called "validate".
"""

from __future__ import annotations

import argparse
import re
from collections.abc import Callable

import pytest

from exabgp.application.main import arguments
from exabgp.application.shell import (
    SUBCOMMANDS,
    generate_bash_completion,
    generate_fish_completion,
    generate_zsh_completion,
)


def _accepted() -> set[str]:
    for action in arguments()._actions:
        if isinstance(action, argparse._SubParsersAction):
            return set(action.choices)
    raise AssertionError('the command line has no subcommands')


def test_subcommands_are_those_the_parser_accepts() -> None:
    assert set(SUBCOMMANDS) == _accepted()


def test_validate_is_not_a_subcommand() -> None:
    assert 'validate' not in SUBCOMMANDS


def _bash() -> list[str]:
    match = re.search(r'local subcommands="([^"]*)"', generate_bash_completion())
    assert match is not None
    return match.group(1).split()


def _zsh_server_fallback() -> list[str]:
    match = re.search(r'if \[\[ ! " ([^"]*) " =~ " \$subcommand " \]\]', generate_zsh_completion())
    assert match is not None
    return match.group(1).split()


def _zsh() -> list[str]:
    block = generate_zsh_completion().split('subcommands=(', 1)[1].split(')', 1)[0]
    return re.findall(r"'([a-z]+):", block)


def _fish_helper() -> list[str]:
    match = re.search(r'set -l subcommands ([a-z ]+)\n', generate_fish_completion())
    assert match is not None
    return match.group(1).split()


def _fish_offered() -> list[str]:
    return re.findall(r"-n 'not __fish_exabgp_using_subcommand' -a '([a-z]+)'", generate_fish_completion())


@pytest.mark.parametrize('listed', [_bash, _zsh_server_fallback, _zsh, _fish_helper, _fish_offered])
def test_each_script_lists_the_subcommands(listed: Callable[[], list[str]]) -> None:
    assert listed() == list(SUBCOMMANDS)
