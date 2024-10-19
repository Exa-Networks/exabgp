# encoding: utf-8
"""
decoder/__init__.py

Created by Thomas Mangin on 2009-08-25.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from exabgp.configuration.core.format import formated
from exabgp.configuration.operational.parser import operational

from exabgp.protocol.family import AFI
from exabgp.protocol.family import SAFI
from exabgp.protocol.family import Family

from exabgp.bgp.message.refresh import RouteRefresh

from exabgp.logger import log
from exabgp.reactor.api.command import Command
from exabgp.configuration.configuration import Configuration

# ======================================================================= Parser
#


class API(Command):
    def __init__(self, reactor):
        self.reactor = reactor
        self.configuration = Configuration([])

    def log_message(self, message, level='INFO'):
        log.info(message, 'processes', level)

    def log_failure(self, message, level='ERR'):
        error = str(self.configuration.tokeniser.error)
        report = '%s\nreason: %s' % (message, error) if error else message
        log.error(report, 'processes', level)

    def process(self, reactor, service, command):
        use_json = False
        # it to allow a global "set encoding json"
        # it to allow a global "set encoding text"
        # to not have to set the encoding on each command
        if 'json' in command.split(' '):
            use_json = True
        return self.response(reactor, service, command, use_json)

    def response(self, reactor, service, command, use_json):
        api = 'json' if use_json else 'text'
        for registered in self.functions:
            if registered == command or command.endswith(' ' + registered) or registered + ' ' in command:
                return self.callback[api][registered](self, reactor, service, command, use_json)
        reactor.processes.answer_error(service)
        log.warning('command from process not understood : %s' % command, 'api')
        return False

    def api_route(self, command):
        action, line = command.split(' ', 1)

        self.configuration.static.clear()
        if not self.configuration.partial('static', line, action):
            return []

        if self.configuration.scope.location():
            return []

        self.configuration.scope.to_context()
        changes = self.configuration.scope.pop_routes()
        return changes

    def api_announce_v4(self, command):
        action, line = command.split(' ', 1)
        _, line = line.split(' ', 1)

        self.configuration.static.clear()
        if not self.configuration.partial('ipv4', line, action):
            return []

        if self.configuration.scope.location():
            return []

        self.configuration.scope.to_context()
        changes = self.configuration.scope.pop_routes()
        return changes

    def api_announce_v6(self, command):
        action, line = command.split(' ', 1)
        _, line = line.split(' ', 1)

        self.configuration.static.clear()
        if not self.configuration.partial('ipv6', line, action):
            return []

        if self.configuration.scope.location():
            return []

        self.configuration.scope.to_context()
        changes = self.configuration.scope.pop_routes()
        return changes

    def api_flow(self, command):
        action, flow, line = command.split(' ', 2)

        self.configuration.flow.clear()
        if not self.configuration.partial('flow', line):
            return []

        if self.configuration.scope.location():
            return []

        self.configuration.scope.to_context()
        changes = self.configuration.scope.pop_routes()
        return changes

    def api_vpls(self, command):
        action, line = command.split(' ', 1)

        self.configuration.l2vpn.clear()
        if not self.configuration.partial('l2vpn', line):
            return []

        self.configuration.scope.to_context()
        changes = self.configuration.scope.pop_routes()
        return changes

    def api_attributes(self, command, peers):
        action, line = command.split(' ', 1)

        self.configuration.static.clear()
        if not self.configuration.partial('static', line):
            return []

        if self.configuration.scope.location():
            return []

        self.configuration.scope.to_context()
        changes = self.configuration.scope.pop_routes()
        return changes

    def api_refresh(self, command):
        tokens = formated(command).split(' ')[2:]
        if len(tokens) != 2:
            return False
        afi = AFI.value(tokens.pop(0))
        safi = SAFI.value(tokens.pop(0))
        if afi is None or safi is None:
            return False
        return [RouteRefresh(afi, safi)]

    def api_eor(self, command):
        tokens = formated(command).split(' ')[2:]
        number = len(tokens)

        if not number:
            return Family(1, 1)

        if number != 2:
            return False

        afi = AFI.fromString(tokens[0])
        if afi == AFI.undefined:
            return False

        safi = SAFI.fromString(tokens[1])
        if safi == SAFI.undefined:
            return False

        return Family(afi, safi)

    def api_operational(self, command):
        tokens = formated(command).split(' ')

        op = tokens[1].lower()
        what = tokens[2].lower()

        if op != 'operational':
            return False

        self.configuration.tokeniser.iterate.replenish(tokens[3:])
        # None or a class
        return operational(what, self.configuration.tokeniser.iterate)
