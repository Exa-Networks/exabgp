"""Every API route command of the functional tests reads the same with the legacy parser and the grammar.

The command is read as Configuration.partial() reads it for the API: one statement of the
static section, announced or withdrawn.
"""

from __future__ import annotations

import glob
import os
import re

import pytest

from exabgp.configuration.compare import route_state
from exabgp.configuration.configuration import Configuration
from exabgp.configuration.grammar.engine import NotMigrated
from exabgp.configuration.grammar.read import read_command

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
COMMAND = re.compile(r'^\d+:cmd:(announce|withdraw) ((?:route|attributes?|ipv4|ipv6) .*)$')


def section(line: str) -> tuple[str, str]:
    """The section partial() is given, and the text: `ipv4 unicast ...` is `unicast ...` of ipv4."""
    first, _, rest = line.partition(' ')
    if first in ('ipv4', 'ipv6'):
        return first, rest
    return 'static', line


def _commands() -> list[tuple[str, str]]:
    found: dict[tuple[str, str], None] = {}
    for path in sorted(glob.glob(os.path.join(ROOT, 'qa', '*', '*.ci'))):
        with open(path) as handle:
            for line in handle:
                match = COMMAND.match(line.strip())
                if match:
                    found[(match.group(1), match.group(2))] = None
    return list(found)


COMMANDS = _commands()


def legacy(action: str, line: str) -> list[tuple[object, ...]] | str:
    configuration = Configuration([''], text=True)
    try:
        accepted = configuration.partial(*section(line), action)
    except AttributeError:
        # legacy: an announce family builds `originator-id` as an address, which the attribute
        # collection can not take, and the exception leaves partial(): the command fails
        return 'rejected'
    if not accepted:
        return 'rejected'
    configuration.scope.to_context()
    return [route_state(route) for route in configuration.scope.pop_routes()]


def grammar(action: str, line: str) -> list[tuple[object, ...]] | str:
    try:
        routes = read_command(*section(line), action == 'announce')
    except NotMigrated as exc:
        pytest.skip(str(exc).split(': ', 1)[-1])
    except ValueError:
        return 'rejected'
    return [route_state(route) for route in routes]


@pytest.mark.parametrize('action,line', COMMANDS, ids=[f'{action} {line}' for action, line in COMMANDS])
def test_an_api_command_reads_the_same_with_both_parsers(action: str, line: str) -> None:
    assert grammar(action, line) == legacy(action, line)


def test_the_commands_were_found() -> None:
    assert len(COMMANDS) > 100
