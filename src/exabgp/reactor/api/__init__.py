"""api/__init__.py

API command processing.

Created by Thomas Mangin on 2009-08-25.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from exabgp.reactor.loop import Reactor

from exabgp.configuration.core.format import formated
from exabgp.configuration.operational.parser import operational

from exabgp.protocol.family import AFI
from exabgp.protocol.family import SAFI
from exabgp.protocol.family import Family

from exabgp.bgp.message.refresh import RouteRefresh
from exabgp.bgp.message import Operational
from exabgp.rib.route import Route

from exabgp.environment import getenv
from exabgp.logger import log, lazyexc, lazymsg
from exabgp.reactor.api.dispatch import dispatch_v4, dispatch_v6, UnknownCommand, NoMatchingPeers
from exabgp.configuration.configuration import Configuration

# API command parsing constants
API_REFRESH_TOKEN_COUNT = 2  # Refresh command requires 2 tokens (AFI and SAFI)
API_EOR_TOKEN_COUNT = 2  # EOR command requires 2 tokens (AFI and SAFI)

# ======================================================================= Parser
#


class API:
    def __init__(self, reactor: 'Reactor') -> None:
        self.reactor: 'Reactor' = reactor
        self.configuration: Configuration = Configuration([])

    def log_message(self, message: str, level: str = 'INFO') -> None:
        log.info(lazymsg('api.message content={message}', message=message), 'processes', level)

    def log_failure(self, message: str, level: str = 'ERR') -> None:
        error = str(self.configuration.error)
        report = '{}\nreason: {}'.format(message, error) if error else message
        log.error(lazymsg('api.failure report={report}', report=report), 'processes', level)

    def log_exception(self, message: str, exc: BaseException, level: str = 'ERR') -> None:
        """Log a failure with full traceback when debug mode (-d) is enabled."""
        error = str(self.configuration.error)
        report = '{}\nreason: {}'.format(message, error) if error else message
        log.error(lazyexc('api.failure report={report} error={exc}', exc, report=report), 'processes', level)

    def process(self, reactor: 'Reactor', service: str, command: str) -> bool:
        """Process an API command (sync version).

        Uses parallel v4/v6 dispatchers based on API version setting.
        """
        api_version = getenv().api.version

        # v6 API is JSON-only, v4 API checks for 'json' as last word
        if api_version == 6:
            use_json = True
        else:
            words = command.split()
            use_json = words[-1] == 'json' if words else False

        try:
            if api_version == 4:
                handler, peers, remaining = dispatch_v4(command, reactor, service)
            else:
                handler, peers, remaining = dispatch_v6(command, reactor, service)
            return handler(self, reactor, service, peers, remaining, use_json)
        except UnknownCommand:
            log.warning(lazymsg('api.command.unknown command={command}', command=command), 'api')
            reactor.processes.answer_error(service)
            return False
        except NoMatchingPeers:
            log.warning(lazymsg('api.command.no_peers command={command}', command=command), 'api')
            reactor.processes.answer_error(service)
            return False

    async def process_async(self, reactor: 'Reactor', service: str, command: str) -> bool:
        """Process an API command (async version).

        Uses parallel v4/v6 dispatchers based on API version setting.
        After calling the handler, flush any queued writes immediately.
        """
        api_version = getenv().api.version

        # v6 API is JSON-only, v4 API checks for 'json' as last word
        if api_version == 6:
            use_json = True
        else:
            words = command.split()
            use_json = words[-1] == 'json' if words else False

        try:
            if api_version == 4:
                handler, peers, remaining = dispatch_v4(command, reactor, service)
            else:
                handler, peers, remaining = dispatch_v6(command, reactor, service)
            result = handler(self, reactor, service, peers, remaining, use_json)
            # Flush any queued writes immediately
            await reactor.processes.flush_write_queue_async()
            return bool(result)
        except UnknownCommand:
            log.warning(lazymsg('api.command.unknown command={command}', command=command), 'api')
            reactor.processes.answer_error(service)
            await reactor.processes.flush_write_queue_async()
            return False
        except NoMatchingPeers:
            log.warning(lazymsg('api.command.no_peers command={command}', command=command), 'api')
            reactor.processes.answer_error(service)
            await reactor.processes.flush_write_queue_async()
            return False

    def api_route(self, command: str, action: str = '') -> list[Route]:
        if action:
            # Clean format: command is "route 10.0.0.0/24 ...", action passed separately
            # partial() expects line to include "route ..." so use command as-is
            line = command
        else:
            # Legacy format: command is "announce route 10.0.0.0/24 ..."
            action, line = command.split(' ', 1)

        self.configuration.static.clear()
        if not self.configuration.partial('static', line, action):
            return []

        if self.configuration.scope.location():
            return []

        self.configuration.scope.to_context()
        routes = self.configuration.scope.pop_routes()
        return routes

    def api_announce_v4(self, command: str, action: str = '') -> list[Route]:
        if action:
            # Clean format: command is "ipv4 unicast ...", action passed separately
            _, line = command.split(' ', 1)
        else:
            # Legacy format: command is "announce ipv4 unicast ..."
            action, line = command.split(' ', 1)
            _, line = line.split(' ', 1)

        self.configuration.static.clear()
        if not self.configuration.partial('ipv4', line, action):
            return []

        if self.configuration.scope.location():
            return []

        self.configuration.scope.to_context()
        routes = self.configuration.scope.pop_routes()
        return routes

    def api_announce_v6(self, command: str, action: str = '') -> list[Route]:
        if action:
            # Clean format: command is "ipv6 unicast ...", action passed separately
            _, line = command.split(' ', 1)
        else:
            # Legacy format: command is "announce ipv6 unicast ..."
            action, line = command.split(' ', 1)
            _, line = line.split(' ', 1)

        self.configuration.static.clear()
        if not self.configuration.partial('ipv6', line, action):
            return []

        if self.configuration.scope.location():
            return []

        self.configuration.scope.to_context()
        routes = self.configuration.scope.pop_routes()
        return routes

    def api_flow(self, command: str, action: str = '') -> list[Route]:
        if action:
            # Clean format: command is "flow match ...", action passed separately
            _, line = command.split(' ', 1)
        else:
            # Legacy format: command is "announce flow match ..."
            action, _, line = command.split(' ', 2)

        self.configuration.flow.clear()
        if not self.configuration.partial('flow', line):
            return []

        if self.configuration.scope.location():
            return []

        self.configuration.scope.to_context()
        routes = self.configuration.scope.pop_routes()
        return routes

    def api_vpls(self, command: str, action: str = '') -> list[Route]:
        if action:
            # Clean format: command is "vpls ...", action passed separately
            # partial() expects line to include "vpls ..." so use command as-is
            line = command
        else:
            # Legacy format: command is "announce vpls ..."
            action, line = command.split(' ', 1)

        self.configuration.l2vpn.clear()
        if not self.configuration.partial('l2vpn', line):
            return []

        self.configuration.scope.to_context()
        routes = self.configuration.scope.pop_routes()
        return routes

    def api_attributes(self, command: str, peers: list[str], action: str = '') -> list[Route]:
        if action:
            # Clean format: command is "attribute ...", action passed separately
            # partial() expects line to include "attribute ..." so use command as-is
            line = command
        else:
            # Legacy format: command is "announce attribute ..."
            action, line = command.split(' ', 1)

        self.configuration.static.clear()
        if not self.configuration.partial('static', line):
            return []

        if self.configuration.scope.location():
            return []

        self.configuration.scope.to_context()
        routes = self.configuration.scope.pop_routes()
        return routes

    def api_refresh(self, command: str, action: str = '') -> list[RouteRefresh] | None:
        if action:
            # Clean format: command is "route-refresh ipv4 unicast", action passed separately
            tokens = formated(command).split(' ')[1:]  # skip "route-refresh"
        else:
            # Legacy format: command is "announce route-refresh ipv4 unicast"
            tokens = formated(command).split(' ')[2:]  # skip "announce route-refresh"
        if len(tokens) != API_REFRESH_TOKEN_COUNT:
            return None
        afi = AFI.value(tokens.pop(0))
        safi = SAFI.value(tokens.pop(0))
        if afi is None or safi is None:
            return None
        return [RouteRefresh.make_route_refresh(afi, safi)]

    def api_eor(self, command: str, action: str = '') -> bool | Family:
        if action:
            # Clean format: command is "eor [ipv4 unicast]", action passed separately
            tokens = formated(command).split(' ')[1:]  # skip "eor"
        else:
            # Legacy format: command is "announce eor [ipv4 unicast]"
            tokens = formated(command).split(' ')[2:]  # skip "announce eor"
        number = len(tokens)

        if not number:
            return Family(1, 1)

        if number != API_EOR_TOKEN_COUNT:
            return False

        afi = AFI.from_string(tokens[0])
        if afi == AFI.undefined:
            return False

        safi = SAFI.from_string(tokens[1])
        if safi == SAFI.undefined:
            return False

        return Family(afi, safi)

    def api_operational(self, command: str, action: str = '') -> bool | Operational | None:
        tokens = formated(command).split(' ')

        if action:
            # Clean format: command is "operational asm ...", action passed separately
            op = tokens[0].lower()
            what = tokens[1].lower()
            rest = tokens[2:]
        else:
            # Legacy format: command is "announce operational asm ..."
            op = tokens[1].lower()
            what = tokens[2].lower()
            rest = tokens[3:]

        if op != 'operational':
            return False

        self.configuration.tokeniser.replenish(rest)
        # None or a class
        return operational(what, self.configuration.tokeniser)
