"""line/watchdog.py

Created by Thomas Mangin on 2017-07-01.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import asyncio

from exabgp.reactor.api.command.command import Command


def register_watchdog():
    pass


@Command.register('announce watchdog', json_support=True)
def announce_watchdog(self, reactor, service, line, use_json):
    async def callback(name):
        # XXX: move into Action
        for neighbor_name in reactor.configuration.neighbors.keys():
            neighbor = reactor.configuration.neighbors.get(neighbor_name, None)
            if not neighbor:
                continue
            neighbor.rib.outgoing.announce_watchdog(name)
            await asyncio.sleep(0)  # Yield control after each neighbor (matches original yield False)

        await reactor.processes.answer_done_async(service)

    try:
        name = line.split(' ')[2]
    except IndexError:
        name = service
    reactor.asynchronous.schedule(service, line, callback(name))
    return True


@Command.register('withdraw watchdog', json_support=True)
def withdraw_watchdog(self, reactor, service, line, use_json):
    async def callback(name):
        # XXX: move into Action
        for neighbor_name in reactor.configuration.neighbors.keys():
            neighbor = reactor.configuration.neighbors.get(neighbor_name, None)
            if not neighbor:
                continue
            neighbor.rib.outgoing.withdraw_watchdog(name)
            await asyncio.sleep(0)  # Yield control after each neighbor (matches original yield False)

        await reactor.processes.answer_done_async(service)

    try:
        name = line.split(' ')[2]
    except IndexError:
        name = service
    reactor.asynchronous.schedule(service, line, callback(name))
    return True
