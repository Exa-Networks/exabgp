# encoding: utf-8
"""
line/reactor.py

Created by Thomas Mangin on 2017-07-01.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from exabgp.version import version as _version
from exabgp.reactor.api.command.command import Command


def register_reactor():
    pass


@Command.register('text', 'help', False)
def manual(self, reactor, service, _):
    lines = []
    for command in sorted(self.callback['text']):
        if self.callback['options'][command]:
            extended = '%s [ %s ]' % (command, ' | '.join(self.callback['options'][command]))
        else:
            extended = command
        lines.append('[neighbor <ip> [filters]] ' + command if self.callback['neighbor'][command] else '%s ' % extended)

    reactor.processes.write(service, '', True)
    reactor.processes.write(service, 'available API commands are listed here:', True)
    reactor.processes.write(service, '=======================================', True)
    reactor.processes.write(service, '', True)
    reactor.processes.write(
        service, 'filter can be: [local-ip <ip>][local-as <asn>][peer-as <asn>][router-id <router-id>]', True
    )
    reactor.processes.write(service, '', True)
    reactor.processes.write(service, 'command are:', True)
    reactor.processes.write(service, '------------', True)
    reactor.processes.write(service, '', True)
    for line in sorted(lines):
        reactor.processes.write(service, line, True)
    reactor.processes.write(service, '', True)
    reactor.processes.answer_done(service)
    return True


@Command.register('text', 'shutdown', False)
def shutdown(self, reactor, service, _):
    reactor.signal.received = reactor.signal.SHUTDOWN
    reactor.processes.write(service, 'shutdown in progress')
    reactor.processes.answer_done(service)
    return True


@Command.register('text', 'reload', False)
def reload(self, reactor, service, _):
    reactor.signal.received = reactor.signal.RELOAD
    reactor.processes.write(service, 'reload in progress')
    reactor.processes.answer_done(service)
    return True


@Command.register('text', 'restart', False)
def restart(self, reactor, service, _):
    reactor.signal.received = reactor.signal.RESTART
    reactor.processes.write(service, 'restart in progress')
    reactor.processes.answer_done(service)
    return True


@Command.register('text', 'version', False)
def version(self, reactor, service, _):
    reactor.processes.write(service, 'exabgp %s' % _version)
    reactor.processes.answer_done(service)
    return True


@Command.register('text', '#', False)
def comment(self, reactor, service, line):
    self.logger.debug(line.lstrip().lstrip('#').strip(), 'process')
    reactor.processes.answer_done(service)
    return True


@Command.register('text', 'reset', False)
def reset(self, reactor, service, line):
    reactor.asynchronous.clear(service)


@Command.register('text', 'crash')
def crash(self, reactor, service, line):
    def callback():
        raise ValueError('crash test of the API')
        yield None

    reactor.asynchronous.schedule(service, line, callback())
    return True
