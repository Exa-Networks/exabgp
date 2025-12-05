"""line/watchdog.py

Created by Thomas Mangin on 2017-07-01.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from exabgp.reactor.api.command.command import Command

if TYPE_CHECKING:
    from exabgp.reactor.loop import Reactor


def register_watchdog() -> None:
    pass


def _extract_watchdog_name(line: str, service: str) -> str:
    """Extract watchdog name from command line.

    Handles both v4 and v6 formats:
    - v4: 'announce watchdog <name>' or 'withdraw watchdog <name>'
    - v6: 'peer * announce watchdog <name>' or 'peer <ip> withdraw watchdog <name>'
    """
    words = line.split()
    try:
        # Find 'watchdog' and get the next word
        idx = words.index('watchdog')
        if idx + 1 < len(words):
            return words[idx + 1]
    except (ValueError, IndexError):
        pass
    return service


@Command.register('announce watchdog', json_support=True)
def announce_watchdog(self: Command, reactor: Reactor, service: str, line: str, use_json: bool) -> bool:
    async def callback(name: str) -> None:
        # XXX: move into Action
        for neighbor_name in reactor.configuration.neighbors.keys():
            neighbor = reactor.configuration.neighbors.get(neighbor_name, None)
            if not neighbor:
                continue
            neighbor.rib.outgoing.announce_watchdog(name)
            await asyncio.sleep(0)  # Yield control after each neighbor (matches original yield False)

        await reactor.processes.answer_done_async(service)

    name = _extract_watchdog_name(line, service)
    reactor.asynchronous.schedule(service, line, callback(name))
    return True


@Command.register('withdraw watchdog', json_support=True)
def withdraw_watchdog(self: Command, reactor: Reactor, service: str, line: str, use_json: bool) -> bool:
    async def callback(name: str) -> None:
        # XXX: move into Action
        for neighbor_name in reactor.configuration.neighbors.keys():
            neighbor = reactor.configuration.neighbors.get(neighbor_name, None)
            if not neighbor:
                continue
            neighbor.rib.outgoing.withdraw_watchdog(name)
            await asyncio.sleep(0)  # Yield control after each neighbor (matches original yield False)

        await reactor.processes.answer_done_async(service)

    name = _extract_watchdog_name(line, service)
    reactor.asynchronous.schedule(service, line, callback(name))
    return True
