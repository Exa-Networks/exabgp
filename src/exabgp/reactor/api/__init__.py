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

from exabgp.reactor.api.tokeniser import formated
from exabgp.configuration.grammar.read import read_operational

from exabgp.protocol.family import AFI
from exabgp.protocol.family import SAFI
from exabgp.protocol.family import Family

from exabgp.bgp.message.refresh import RouteRefresh
from exabgp.bgp.message import Operational
from exabgp.rib.route import Route

from exabgp.logger import log, lazyexc, lazymsg
from exabgp.reactor.api.dispatch import UnknownCommand, NoMatchingPeers
from exabgp.reactor.api.dispatch.version import API_V6, dispatch_for
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

    @staticmethod
    def _answers_in_json(api_version: int, command: str) -> bool:
        """v6 answers in JSON; v4, and a helper still undecided, only when the command ends in `json`."""
        if api_version == API_V6:
            return True
        words = command.split()
        return words[-1] == 'json' if words else False

    def process(self, reactor: 'Reactor', service: str, command: str) -> bool:
        """Process an API command (sync version).

        Uses parallel v4/v6 dispatchers based on API version setting.
        """
        from exabgp.reactor.api.command import group as group_cmd

        api_version = reactor.processes.detect_api_version(service, command)
        use_json = self._answers_in_json(api_version, command)

        # Check if we're in group mode and this is an announce/withdraw command
        # (not group end which should be processed normally)
        if group_cmd.is_grouping(service):
            cmd_lower = command.strip().lower()
            if cmd_lower.startswith('group end') or cmd_lower.startswith('group start'):
                pass  # Process normally
            elif cmd_lower.startswith('announce') or cmd_lower.startswith('withdraw'):
                # Buffer the command for later processing
                # For multi-line groups, we use all peers (selector was on group start)
                peers = list(reactor.peers(service))
                group_cmd.group_add_command(self, reactor, service, peers, command, use_json)
                return True

        try:
            handler, peers, remaining = dispatch_for(
                reactor.processes.dispatch_version(service), command, reactor, service
            )
            return handler(self, reactor, service, peers, remaining, use_json)
        except UnknownCommand:
            log.warning(lazymsg('api.command.unknown command={command}', command=command), 'api')
            reactor.processes.answer_error_sync(service)
            return False
        except NoMatchingPeers:
            log.warning(lazymsg('api.command.no_peers command={command}', command=command), 'api')
            reactor.processes.answer_error_sync(service)
            return False

    async def process_async(self, reactor: 'Reactor', service: str, command: str) -> bool:
        """Process an API command (async version).

        Uses parallel v4/v6 dispatchers based on API version setting.
        After calling the handler, flush any queued writes immediately.
        """
        from exabgp.reactor.api.command import group as group_cmd

        api_version = reactor.processes.detect_api_version(service, command)
        use_json = self._answers_in_json(api_version, command)

        # Check if we're in group mode and this is an announce/withdraw command
        # (not group end which should be processed normally)
        if group_cmd.is_grouping(service):
            cmd_lower = command.strip().lower()
            if cmd_lower.startswith('group end') or cmd_lower.startswith('group start'):
                pass  # Process normally
            elif cmd_lower.startswith('announce') or cmd_lower.startswith('withdraw'):
                # Buffer the command for later processing
                # For multi-line groups, we use all peers (selector was on group start)
                peers = list(reactor.peers(service))
                group_cmd.group_add_command(self, reactor, service, peers, command, use_json)
                await reactor.processes.flush_write_queue()
                return True

        try:
            handler, peers, remaining = dispatch_for(
                reactor.processes.dispatch_version(service), command, reactor, service
            )
            result = handler(self, reactor, service, peers, remaining, use_json)
            # Flush any queued writes immediately
            await reactor.processes.flush_write_queue()
            return bool(result)
        except UnknownCommand:
            log.warning(lazymsg('api.command.unknown command={command}', command=command), 'api')
            reactor.processes.answer_error_sync(service)
            await reactor.processes.flush_write_queue()
            return False
        except NoMatchingPeers:
            log.warning(lazymsg('api.command.no_peers command={command}', command=command), 'api')
            reactor.processes.answer_error_sync(service)
            await reactor.processes.flush_write_queue()
            return False

    def api_route(self, command: str, action: str = '') -> list[Route]:
        if action:
            # Clean format: command is "route 10.0.0.0/24 ...", action passed separately
            # partial() expects line to include "route ..." so use command as-is
            line = command
        else:
            # Legacy format: command is "announce route 10.0.0.0/24 ..."
            action, line = command.split(' ', 1)

        if not self.configuration.partial('static', line, action):
            return []

        if self.configuration.open_sections:
            return []

        return self.configuration.pop_routes()

    def api_announce_v4(self, command: str, action: str = '') -> list[Route]:
        if action:
            # Clean format: command is "ipv4 unicast ...", action passed separately
            _, line = command.split(' ', 1)
        else:
            # Legacy format: command is "announce ipv4 unicast ..."
            action, line = command.split(' ', 1)
            _, line = line.split(' ', 1)

        if not self.configuration.partial('ipv4', line, action):
            return []

        if self.configuration.open_sections:
            return []

        return self.configuration.pop_routes()

    def api_announce_v6(self, command: str, action: str = '') -> list[Route]:
        if action:
            # Clean format: command is "ipv6 unicast ...", action passed separately
            _, line = command.split(' ', 1)
        else:
            # Legacy format: command is "announce ipv6 unicast ..."
            action, line = command.split(' ', 1)
            _, line = line.split(' ', 1)

        if not self.configuration.partial('ipv6', line, action):
            return []

        if self.configuration.open_sections:
            return []

        return self.configuration.pop_routes()

    def api_flow(self, command: str, action: str = '') -> list[Route]:
        if action:
            # Clean format: command is "flow match ...", action passed separately
            _, line = command.split(' ', 1)
        else:
            # Legacy format: command is "announce flow match ..."
            action, _, line = command.split(' ', 2)

        if not self.configuration.partial('flow', line, action):
            return []

        if self.configuration.open_sections:
            return []

        return self.configuration.pop_routes()

    def api_vpls(self, command: str, action: str = '') -> list[Route]:
        if action:
            # Clean format: command is "vpls ...", action passed separately
            # partial() expects line to include "vpls ..." so use command as-is
            line = command
        else:
            # Legacy format: command is "announce vpls ..."
            action, line = command.split(' ', 1)

        if not self.configuration.partial('l2vpn', line, action):
            return []

        return self.configuration.pop_routes()

    def api_attributes(self, command: str, peers: list[str], action: str = '') -> list[Route]:
        if action:
            # Clean format: command is "attribute ...", action passed separately
            # partial() expects line to include "attribute ..." so use command as-is
            line = command
        else:
            # Legacy format: command is "announce attribute ..."
            action, line = command.split(' ', 1)

        if not self.configuration.partial('static', line, action):
            return []

        if self.configuration.open_sections:
            return []

        return self.configuration.pop_routes()

    def api_refresh(self, command: str, action: str = '') -> list[RouteRefresh] | None:
        if action:
            # Clean format: command is "route-refresh ipv4 unicast", action passed separately
            tokens = formated(command).split(' ')[1:]  # skip "route-refresh"
        else:
            # Legacy format: command is "announce route-refresh ipv4 unicast"
            tokens = formated(command).split(' ')[2:]  # skip "announce route-refresh"
        if len(tokens) != API_REFRESH_TOKEN_COUNT:
            return None
        afi = AFI.from_name(tokens.pop(0))
        safi = SAFI.from_name(tokens.pop(0))
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
            return Family(AFI.ipv4, SAFI.unicast)

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

        # None or a class
        message: Operational | None = read_operational(what, rest)
        return message
