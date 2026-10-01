"""dispatch/version.py

Which API version a helper speaks, worked out from the commands it writes.

A helper written for ExaBGP 5.x writes `announce route ...`, one written for 6.0 writes
`peer * announce route ...`. The two forms share no first word except `group`, so the first
command whose first word belongs to one of them tells which API the helper was written for,
and every later command of that helper is held to it.

Copyright (c) 2009-2026 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from exabgp.reactor.api.dispatch.common import Handler, UnknownCommand
from exabgp.reactor.api.dispatch.v4 import dispatch_v4, translate_v4_to_v6
from exabgp.reactor.api.dispatch.v6 import dispatch_v6

if TYPE_CHECKING:
    from exabgp.reactor.loop import Reactor

# exabgp.api.version when it is not set: each helper's version is detected
API_AUTO = 0
API_V4 = 4
API_V6 = 6

# the first words of the v6 commands; no v4 command starts with one of them
V6_ROOTS = frozenset({'daemon', 'session', 'system', 'rib', 'peer'})


def command_api_version(command: str) -> int:
    """The API version a command is written for, or API_AUTO when it does not tell.

    A v4 command is one the v4 dispatcher knows: `neighbor ...`, or one with a v6
    translation. A command neither dispatcher knows decides nothing, so a typing mistake
    in a helper's first command does not hold the helper to the wrong version.
    """
    words = command.split()
    if not words or words[0].startswith('#'):
        return API_AUTO
    if words[0] in V6_ROOTS:
        return API_V6
    if words[0] == 'neighbor' or translate_v4_to_v6(command) is not None:
        return API_V4
    return API_AUTO


def dispatch_for(
    version: int,
    command: str,
    reactor: 'Reactor',
    service: str,
) -> tuple[Handler, list[str], str]:
    """Dispatch a command with the dispatcher of the helper's API version.

    A helper is held to its version: a v4 helper writing a v6 command gets the same
    UnknownCommand as a v6 helper writing a v4 one. Before the version is known, the v4
    dispatcher is used, as it accepts both forms.

    `group` is the v6 dispatcher's whatever the version: what it groups is the v4
    `announce ...` and `withdraw ...`, so a v4 helper has to be able to use it.
    """
    assert version in (API_AUTO, API_V4, API_V6), f'unknown API version {version}'
    words = command.split()
    if version == API_V6 or (words and words[0] == 'group'):
        return dispatch_v6(command, reactor, service)
    if version == API_V4 and command_api_version(command) == API_V6:
        raise UnknownCommand(command)
    return dispatch_v4(command, reactor, service)
