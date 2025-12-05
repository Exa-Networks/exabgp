"""line/watchdog.py

Created by Thomas Mangin on 2017-07-01.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from exabgp.reactor.api import API
    from exabgp.reactor.loop import Reactor


def register_watchdog() -> None:
    pass


def _extract_watchdog_name(command: str, service: str) -> str:
    """Extract watchdog name from command.

    command may contain:
    - "announce watchdog <name>" (full format from dispatcher)
    - "withdraw watchdog <name>" (full format from dispatcher)
    - "watchdog <name>" (legacy format)
    - "<name>" (name only)
    """
    words = command.split()
    # Skip 'announce' or 'withdraw' prefix if present
    if words and words[0] in ('announce', 'withdraw'):
        words = words[1:]
    # Now first word should be 'watchdog', second is the name
    if len(words) >= 2 and words[0] == 'watchdog':
        return words[1]
    elif len(words) >= 1 and words[0] != 'watchdog':
        # Name directly provided (no watchdog prefix)
        return words[0]
    return service


def announce_watchdog(
    self: 'API', reactor: 'Reactor', service: str, peers: list[str], command: str, use_json: bool
) -> bool:
    async def callback(name: str) -> None:
        # XXX: move into Action
        for neighbor_name in reactor.configuration.neighbors.keys():
            neighbor = reactor.configuration.neighbors.get(neighbor_name, None)
            if not neighbor:
                continue
            neighbor.rib.outgoing.announce_watchdog(name)
            await asyncio.sleep(0)  # Yield control after each neighbor (matches original yield False)

        await reactor.processes.answer_done_async(service)

    name = _extract_watchdog_name(command, service)
    reactor.asynchronous.schedule(service, command, callback(name))
    return True


def withdraw_watchdog(
    self: 'API', reactor: 'Reactor', service: str, peers: list[str], command: str, use_json: bool
) -> bool:
    async def callback(name: str) -> None:
        # XXX: move into Action
        for neighbor_name in reactor.configuration.neighbors.keys():
            neighbor = reactor.configuration.neighbors.get(neighbor_name, None)
            if not neighbor:
                continue
            neighbor.rib.outgoing.withdraw_watchdog(name)
            await asyncio.sleep(0)  # Yield control after each neighbor (matches original yield False)

        await reactor.processes.answer_done_async(service)

    name = _extract_watchdog_name(command, service)
    reactor.asynchronous.schedule(service, command, callback(name))
    return True
