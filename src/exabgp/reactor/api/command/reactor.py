
"""line/reactor.py

Created by Thomas Mangin on 2017-07-01.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from exabgp.version import version as _version
from exabgp.reactor.api.command.command import Command

from exabgp.logger import log


def register_reactor():
    pass


@Command.register('help', False)
def manual(self, reactor, service, line, use_json):
    lines = []
    encoding = 'json' if use_json else 'text'
    for command in sorted(self.callback[encoding]):
        if self.callback['options'][command]:
            options = ' | '.join(self.callback['options'][command])
            extended = f'{command} [ {options} ]'
        else:
            extended = command
        lines.append('[neighbor <ip> [filters]] ' + command if self.callback['neighbor'][command] else f'{extended} ')

    reactor.processes.write(service, '', True)
    reactor.processes.write(service, 'available API commands are listed here:', True)
    reactor.processes.write(service, '=======================================', True)
    reactor.processes.write(service, '', True)
    reactor.processes.write(
        service, 'filter can be: [local-ip <ip>][local-as <asn>][peer-as <asn>][router-id <router-id>]', True,
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


@Command.register('shutdown', False)
def shutdown(self, reactor, service, line, use_json):
    reactor.signal.received = reactor.signal.SHUTDOWN
    reactor.processes.write(service, 'shutdown in progress')
    reactor.processes.answer_done(service)
    return True


@Command.register('reload', False)
def reload(self, reactor, service, line, use_json):
    reactor.signal.received = reactor.signal.RELOAD
    reactor.processes.write(service, 'reload in progress')
    reactor.processes.answer_done(service)
    return True


@Command.register('restart', False)
def restart(self, reactor, service, line, use_json):
    reactor.signal.received = reactor.signal.RESTART
    reactor.processes.write(service, 'restart in progress')
    reactor.processes.answer_done(service)
    return True


@Command.register('version', False)
def version(self, reactor, service, line, use_json):
    reactor.processes.write(service, f'exabgp {_version}')
    reactor.processes.answer_done(service)
    return True


@Command.register('#', False)
def comment(self, reactor, service, line, use_json):
    log.debug(lambda: line.lstrip().lstrip('#').strip(), 'process')
    reactor.processes.answer_done(service)
    return True


@Command.register('reset', False)
def reset(self, reactor, service, line, use_json):
    reactor.asynchronous.clear(service)


@Command.register('crash')
def crash(self, reactor, service, line, use_json):
    def callback():
        raise ValueError('crash test of the API')
        yield None

    reactor.asynchronous.schedule(service, line, callback())
    return True
