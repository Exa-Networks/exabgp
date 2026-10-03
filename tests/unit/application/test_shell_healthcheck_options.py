"""The completion scripts offer the options `exabgp healthcheck` accepts, and no other.

The options were written into each script by hand, from another program: `--nexthop`,
`--local-ip`, `--slow-interval`, `--rd`, `--origin`, `--logging`, `--daemonize` and others were
offered and refused, while `--fall`, `--withdraw-on-down`, `--neighbor` and most of the real ones
were never offered. The scripts now read the options from healthcheck's own parser.
"""

from __future__ import annotations

import argparse
import re
from collections.abc import Callable

import pytest

from exabgp.application import healthcheck
from exabgp.application.shell import generate_bash_completion, generate_fish_completion, generate_zsh_completion


def _accepted() -> set[str]:
    parser = argparse.ArgumentParser(add_help=False)
    healthcheck.setargs(parser)
    return {name for action in parser._actions for name in action.option_strings if name.startswith('--')}


def _section(script: str) -> str:
    start = script.index('        healthcheck)')
    return script[start : script.index('        server)', start)]


def _bash() -> str:
    return _section(generate_bash_completion())


def _zsh() -> str:
    return _section(generate_zsh_completion())


def _fish() -> str:
    lines = generate_fish_completion().splitlines()
    return '\n'.join(line for line in lines if 'from healthcheck' in line).replace(' -l ', ' --')


@pytest.mark.parametrize('section', [_bash, _zsh, _fish])
def test_each_script_offers_the_options_healthcheck_accepts(section: Callable[[], str]) -> None:
    offered = set(re.findall(r'(?<![\w-])--[a-z][a-z-]*', section())) - {'--help'}
    assert offered == _accepted()


def test_an_option_healthcheck_never_had_is_not_offered() -> None:
    for section in (_bash, _zsh, _fish):
        assert '--nexthop' not in section()
        assert '--daemonize' not in section()
