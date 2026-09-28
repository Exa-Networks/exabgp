"""The inputs of the grammar tests, and how the grammar reads each.

The configurations of the repository, the API route commands of the functional tests, and
the outcome of reading one, as outcome.py reduces it.

Copyright (c) 2009-2026 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import glob
import os
import re

from config_grammar.outcome import Accepted, Outcome, Rejected, agree, read_file, read_text, route_state
from exabgp.configuration.grammar.read import read_command

__all__ = ['Accepted', 'Outcome', 'Rejected', 'agree', 'grammar', 'grammar_file', 'grammar_command']

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
CONFIGURATIONS = sorted(
    glob.glob(os.path.join(ROOT, 'etc', 'exabgp', '*.conf'))
    + glob.glob(os.path.join(ROOT, 'tests', 'unit', 'configuration', 'fixtures', '**', '*.conf'), recursive=True)
)
COMMAND = re.compile(r'^\d+:cmd:(announce|withdraw) ((?:route|attributes?|ipv4|ipv6|flow|vpls) .*)$')


def section(line: str) -> tuple[str, str]:
    """The section partial() is given, and the text: `ipv4 unicast ...` is `unicast ...` of ipv4."""
    first, _, rest = line.partition(' ')
    if first in ('ipv4', 'ipv6', 'flow'):
        return first, rest
    if first == 'vpls':
        return 'l2vpn', line
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


def grammar(text: str) -> Outcome:
    return read_text(text)[0]


def grammar_file(path: str) -> Outcome:
    return read_file(path)[0]


def grammar_command(action: str, line: str) -> list[tuple[object, ...]] | str:
    """The routes of an API command, or `rejected`; the API drops them too when a section is left open."""
    try:
        routes, _ = read_command(*section(line), action == 'announce')
    except ValueError:
        return 'rejected'
    return [route_state(route) for route in routes]
