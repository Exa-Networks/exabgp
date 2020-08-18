# encoding: utf-8
"""
line/watchdog.py

Created by Thomas Mangin on 2017-07-01.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from exabgp.reactor.api.command.command import Command


def register_watchdog():
    pass


@Command.register('text', 'announce watchdog')
def announce_watchdog(self, reactor, service, line):
    def callback(name):
        # XXX: move into Action
        for neighbor_name in reactor.configuration.neighbors.keys():
            neighbor = reactor.configuration.neighbors.get(neighbor_name, None)
            if not neighbor:
                continue
            neighbor.rib.outgoing.announce_watchdog(name)
            yield False

        reactor.processes.answer_done(service)

    try:
        name = line.split(' ')[2]
    except IndexError:
        name = service
    reactor.asynchronous.schedule(service, line, callback(name))
    return True


@Command.register('text', 'withdraw watchdog')
def withdraw_watchdog(self, reactor, service, line):
    def callback(name):
        # XXX: move into Action
        for neighbor_name in reactor.configuration.neighbors.keys():
            neighbor = reactor.configuration.neighbors.get(neighbor_name, None)
            if not neighbor:
                continue
            neighbor.rib.outgoing.withdraw_watchdog(name)
            yield False

        reactor.processes.answer_done(service)

    try:
        name = line.split(' ')[2]
    except IndexError:
        name = service
    reactor.asynchronous.schedule(service, line, callback(name))
    return True
