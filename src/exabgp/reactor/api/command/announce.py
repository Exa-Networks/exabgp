"""line/watchdog.py

Created by Thomas Mangin on 2017-07-01.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from exabgp.reactor.api.command.command import Command
from exabgp.reactor.api.command.limit import match_neighbors
from exabgp.reactor.api.command.limit import extract_neighbors

from exabgp.protocol.ip import IP
from exabgp.protocol.family import Family
from exabgp.bgp.message import Action
from exabgp.bgp.message.operational import Operational
from exabgp.bgp.message.update.attribute import NextHop

from exabgp.configuration.static import ParseStaticRoute
from exabgp.logger import log, lazymsg

if TYPE_CHECKING:
    from exabgp.reactor.api import API
    from exabgp.reactor.loop import Reactor


def register_announce() -> None:
    pass


def parse_sync_mode(command: str, reactor: 'Reactor', service: str) -> tuple[str, bool]:
    """Parse sync/async keyword from command and determine sync mode.

    Handles keywords in any order at end of command:
    - "route 10.0.0.0/24 next-hop 1.2.3.4 sync json"
    - "route 10.0.0.0/24 next-hop 1.2.3.4 json sync"
    - "route 10.0.0.0/24 next-hop 1.2.3.4 sync"
    - "route 10.0.0.0/24 next-hop 1.2.3.4 json"

    Returns:
        (command_stripped, sync_mode) tuple where:
        - command_stripped: command with sync/async/json/text keywords removed
        - sync_mode: True for sync, False for immediate, based on override or service default
    """
    command_parts = command.strip().split()
    sync_override = None

    # Strip trailing keywords in any order (up to 2: encoding + sync mode)
    for _ in range(2):
        if not command_parts:
            break
        last = command_parts[-1]
        if last == 'sync':
            sync_override = True
            command_parts = command_parts[:-1]
        elif last == 'async':
            sync_override = False
            command_parts = command_parts[:-1]
        elif last in ('json', 'text'):
            command_parts = command_parts[:-1]
        else:
            break

    command_stripped = ' '.join(command_parts)

    # Determine sync mode: override if specified, else use service default
    sync_mode = sync_override if sync_override is not None else reactor.processes.get_sync(service)

    return command_stripped, sync_mode


def register_flush_callbacks(peers: list[str], reactor: 'Reactor', sync_mode: bool) -> list[asyncio.Event]:
    """Register flush callbacks for all connected peers if sync mode enabled.

    Returns:
        List of asyncio.Event objects to await (empty if not sync mode)
    """
    flush_events = []
    if sync_mode:
        for peer_key in peers:
            peer = reactor._peers.get(peer_key)
            # Only wait for peers with active session and RIB
            if peer and peer.proto and peer.proto.connection and peer.neighbor.rib:
                event = peer.neighbor.rib.outgoing.register_flush_callback()
                flush_events.append(event)
                log.debug(lazymsg('sync.callback.registered peer={p}', p=peer_key), 'api')
            # Skip peers with session down - don't wait for them
    return flush_events


# @Command.register('debug')
# the command debug is hardcoded in the process code


@Command.register('announce route', json_support=True)
def announce_route(self: 'API', reactor: Reactor, service: str, line: str, use_json: bool) -> bool:
    async def callback() -> None:
        try:
            descriptions, command = extract_neighbors(line)
            peers = match_neighbors(reactor.peers(service), descriptions)
            if not peers:
                error_msg = f'No neighbor matching the command: {command}'
                self.log_failure(error_msg)
                await reactor.processes.answer_error_async(service, error_msg)
                return

            # Parse sync mode and strip keywords
            command, sync_mode = parse_sync_mode(command, reactor, service)

            changes = self.api_route(command)
            if not changes:
                error_msg = f'Could not parse route: {command}'
                self.log_failure(error_msg)
                await reactor.processes.answer_error_async(service, error_msg)
                return

            # Register flush callbacks for connected peers (if sync mode)
            flush_events = register_flush_callbacks(peers, reactor, sync_mode)

            for change in changes:
                if not ParseStaticRoute.check(change):
                    peer_list = ', '.join(peers) if peers else 'all peers'
                    self.log_message(f'invalid route for {peer_list} : {change.extensive()}')
                    continue
                change.nlri.action = Action.ANNOUNCE
                reactor.configuration.inject_change(peers, change)
                peer_list = ', '.join(peers) if peers else 'all peers'
                self.log_message(f'route added to {peer_list} : {change.extensive()}')
                await asyncio.sleep(0)  # Yield control after each route (matches original yield False)

            # Wait for all peers to flush to wire (if sync mode)
            if flush_events:
                await asyncio.gather(*[e.wait() for e in flush_events])

            await reactor.processes.answer_done_async(service)
        except ValueError as e:
            error_msg = f'Failed to parse route: {str(e)}'
            self.log_failure(error_msg)
            await reactor.processes.answer_error_async(service, error_msg)
        except IndexError as e:
            error_msg = f'Invalid route syntax: {str(e)}'
            self.log_failure(error_msg)
            await reactor.processes.answer_error_async(service, error_msg)
        except Exception as e:
            error_msg = f'Unexpected error: {type(e).__name__}: {str(e)}'
            self.log_failure(error_msg)
            await reactor.processes.answer_error_async(service, error_msg)

    reactor.asynchronous.schedule(service, line, callback())
    return True


@Command.register('withdraw route', json_support=True)
def withdraw_route(self: 'API', reactor: Reactor, service: str, line: str, use_json: bool) -> bool:
    async def callback() -> None:
        try:
            descriptions, command = extract_neighbors(line)
            peers = match_neighbors(reactor.peers(service), descriptions)
            if not peers:
                error_msg = f'No neighbor matching the command: {command}'
                self.log_failure(error_msg)
                await reactor.processes.answer_error_async(service, error_msg)
                return

            # Parse sync mode and strip keywords
            command, sync_mode = parse_sync_mode(command, reactor, service)

            changes = self.api_route(command)
            if not changes:
                error_msg = f'Could not parse route: {command}'
                self.log_failure(error_msg)
                await reactor.processes.answer_error_async(service, error_msg)
                return

            # Register flush callbacks for connected peers (if sync mode)
            flush_events = register_flush_callbacks(peers, reactor, sync_mode)

            for change in changes:
                # Change the action to withdraw before checking the route
                change.nlri.action = Action.WITHDRAW
                # NextHop is a mandatory field (but we do not require in)
                if change.nlri.nexthop is IP.NoNextHop:
                    change.nlri.nexthop = NextHop.from_string('0.0.0.0')

                if not ParseStaticRoute.check(change):
                    peer_list = ', '.join(peers) if peers else 'all peers'
                    self.log_message(f'invalid route for {peer_list} : {change.extensive()}')
                    continue
                if reactor.configuration.inject_change(peers, change):
                    peer_list = ', '.join(peers) if peers else 'all peers'
                    self.log_message(f'route removed from {peer_list} : {change.extensive()}')
                else:
                    peer_list = ', '.join(peers) if peers else 'all peers'
                    self.log_failure(f'route not found on {peer_list} : {change.extensive()}')
                await asyncio.sleep(0)  # Yield control after each route (matches original yield False in both branches)

            # Wait for all peers to flush to wire (if sync mode)
            if flush_events:
                await asyncio.gather(*[e.wait() for e in flush_events])

            await reactor.processes.answer_done_async(service)
        except ValueError as e:
            error_msg = f'Failed to parse route: {str(e)}'
            self.log_failure(error_msg)
            await reactor.processes.answer_error_async(service, error_msg)
        except IndexError as e:
            error_msg = f'Invalid route syntax: {str(e)}'
            self.log_failure(error_msg)
            await reactor.processes.answer_error_async(service, error_msg)
        except Exception as e:
            error_msg = f'Unexpected error: {type(e).__name__}: {str(e)}'
            self.log_failure(error_msg)
            await reactor.processes.answer_error_async(service, error_msg)

    reactor.asynchronous.schedule(service, line, callback())
    return True


@Command.register('announce vpls', json_support=True)
def announce_vpls(self: 'API', reactor: Reactor, service: str, line: str, use_json: bool) -> bool:
    async def callback() -> None:
        try:
            descriptions, command = extract_neighbors(line)
            peers = match_neighbors(reactor.peers(service), descriptions)
            if not peers:
                self.log_failure(f'no neighbor matching the command : {command}')
                await reactor.processes.answer_error_async(service)
                return

            # Parse sync mode and strip keywords
            command, sync_mode = parse_sync_mode(command, reactor, service)

            changes = self.api_vpls(command)
            if not changes:
                self.log_failure(f'command could not parse vpls in : {command}')
                await reactor.processes.answer_error_async(service)
                return

            # Register flush callbacks for connected peers (if sync mode)
            flush_events = register_flush_callbacks(peers, reactor, sync_mode)

            for change in changes:
                change.nlri.action = Action.ANNOUNCE
                reactor.configuration.inject_change(peers, change)
                peer_list = ', '.join(peers) if peers else 'all peers'
                self.log_message(f'vpls added to {peer_list} : {change.extensive()}')
                await asyncio.sleep(0)  # Yield control after each route (matches original yield False)

            # Wait for all peers to flush to wire (if sync mode)
            if flush_events:
                await asyncio.gather(*[e.wait() for e in flush_events])

            await reactor.processes.answer_done_async(service)
        except ValueError:
            self.log_failure('issue parsing the vpls')
            await reactor.processes.answer_error_async(service)
        except IndexError:
            self.log_failure('issue parsing the vpls')
            await reactor.processes.answer_error_async(service)

    reactor.asynchronous.schedule(service, line, callback())
    return True


@Command.register('withdraw vpls', json_support=True)
def withdraw_vpls(self: 'API', reactor: Reactor, service: str, line: str, use_json: bool) -> bool:
    async def callback() -> None:
        try:
            descriptions, command = extract_neighbors(line)
            peers = match_neighbors(reactor.peers(service), descriptions)
            if not peers:
                self.log_failure(f'no neighbor matching the command : {command}')
                await reactor.processes.answer_error_async(service)
                return

            # Parse sync mode and strip keywords
            command, sync_mode = parse_sync_mode(command, reactor, service)

            changes = self.api_vpls(command)

            if not changes:
                self.log_failure(f'command could not parse vpls in : {command}')
                await reactor.processes.answer_error_async(service)
                return

            # Register flush callbacks for connected peers (if sync mode)
            flush_events = register_flush_callbacks(peers, reactor, sync_mode)

            for change in changes:
                change.nlri.action = Action.WITHDRAW
                if reactor.configuration.inject_change(peers, change):
                    peer_list = ', '.join(peers) if peers else 'all peers'
                    self.log_message(f'vpls removed from {peer_list} : {change.extensive()}')
                else:
                    peer_list = ', '.join(peers) if peers else 'all peers'
                    self.log_failure(f'vpls not found on {peer_list} : {change.extensive()}')
                await asyncio.sleep(0)  # Yield control after each route (matches original yield False in both branches)

            # Wait for all peers to flush to wire (if sync mode)
            if flush_events:
                await asyncio.gather(*[e.wait() for e in flush_events])

            await reactor.processes.answer_done_async(service)
        except ValueError:
            self.log_failure('issue parsing the vpls')
            await reactor.processes.answer_error_async(service)
        except IndexError:
            self.log_failure('issue parsing the vpls')
            await reactor.processes.answer_error_async(service)

    reactor.asynchronous.schedule(service, line, callback())
    return True


@Command.register('announce attribute', json_support=True)
@Command.register('announce attributes', json_support=True)
def announce_attributes(self: 'API', reactor: Reactor, service: str, line: str, use_json: bool) -> bool:
    async def callback() -> None:
        try:
            descriptions, command = extract_neighbors(line)
            peers = match_neighbors(reactor.peers(service), descriptions)
            if not peers:
                self.log_failure(f'no neighbor matching the command : {command}')
                await reactor.processes.answer_error_async(service)
                return

            # Parse sync mode and strip keywords
            command, sync_mode = parse_sync_mode(command, reactor, service)

            changes = self.api_attributes(command, peers)
            if not changes:
                self.log_failure(f'command could not parse route in : {command}')
                await reactor.processes.answer_error_async(service)
                return

            # Register flush callbacks for connected peers (if sync mode)
            flush_events = register_flush_callbacks(peers, reactor, sync_mode)

            for change in changes:
                change.nlri.action = Action.ANNOUNCE
                reactor.configuration.inject_change(peers, change)
                peer_list = ', '.join(peers) if peers else 'all peers'
                self.log_message(f'route added to {peer_list} : {change.extensive()}')
                await asyncio.sleep(0)  # Yield control after each route (matches original yield False)

            # Wait for all peers to flush to wire (if sync mode)
            if flush_events:
                await asyncio.gather(*[e.wait() for e in flush_events])

            await reactor.processes.answer_done_async(service)
        except ValueError as e:
            error_msg = f'Failed to parse route: {str(e)}'
            self.log_failure(error_msg)
            await reactor.processes.answer_error_async(service, error_msg)
        except IndexError as e:
            error_msg = f'Invalid route syntax: {str(e)}'
            self.log_failure(error_msg)
            await reactor.processes.answer_error_async(service, error_msg)
        except Exception as e:
            error_msg = f'Unexpected error: {type(e).__name__}: {str(e)}'
            self.log_failure(error_msg)
            await reactor.processes.answer_error_async(service, error_msg)

    reactor.asynchronous.schedule(service, line, callback())
    return True


@Command.register('withdraw attribute', json_support=True)
@Command.register('withdraw attributes', json_support=True)
def withdraw_attribute(self: 'API', reactor: Reactor, service: str, line: str, use_json: bool) -> bool:
    async def callback() -> None:
        try:
            descriptions, command = extract_neighbors(line)
            peers = match_neighbors(reactor.peers(service), descriptions)
            if not peers:
                self.log_failure(f'no neighbor matching the command : {command}')
                await reactor.processes.answer_error_async(service)
                return

            # Parse sync mode and strip keywords
            command, sync_mode = parse_sync_mode(command, reactor, service)

            changes = self.api_attributes(command, peers)
            if not changes:
                self.log_failure(f'command could not parse route in : {command}')
                await reactor.processes.answer_error_async(service)
                return

            # Register flush callbacks for connected peers (if sync mode)
            flush_events = register_flush_callbacks(peers, reactor, sync_mode)

            for change in changes:
                change.nlri.action = Action.WITHDRAW
                if reactor.configuration.inject_change(peers, change):
                    peer_list = ', '.join(peers) if peers else 'all peers'
                    self.log_message(f'route removed from {peer_list} : {change.extensive()}')
                    await asyncio.sleep(0)  # Yield control after each route (matches original yield False)
                else:
                    peer_list = ', '.join(peers) if peers else 'all peers'
                    self.log_failure(f'route not found on {peer_list} : {change.extensive()}')
                    await asyncio.sleep(0)  # Yield control after each route (matches original yield False)

            # Wait for all peers to flush to wire (if sync mode)
            if flush_events:
                await asyncio.gather(*[e.wait() for e in flush_events])

            await reactor.processes.answer_done_async(service)
        except ValueError as e:
            error_msg = f'Failed to parse route: {str(e)}'
            self.log_failure(error_msg)
            await reactor.processes.answer_error_async(service, error_msg)
        except IndexError as e:
            error_msg = f'Invalid route syntax: {str(e)}'
            self.log_failure(error_msg)
            await reactor.processes.answer_error_async(service, error_msg)
        except Exception as e:
            error_msg = f'Unexpected error: {type(e).__name__}: {str(e)}'
            self.log_failure(error_msg)
            await reactor.processes.answer_error_async(service, error_msg)

    reactor.asynchronous.schedule(service, line, callback())
    return True


@Command.register('announce flow', json_support=True)
def announce_flow(self: 'API', reactor: Reactor, service: str, line: str, use_json: bool) -> bool:
    async def callback() -> None:
        try:
            descriptions, command = extract_neighbors(line)
            peers = match_neighbors(reactor.peers(service), descriptions)
            if not peers:
                self.log_failure(f'no neighbor matching the command : {command}')
                await reactor.processes.answer_error_async(service)
                return

            # Parse sync mode and strip keywords
            command, sync_mode = parse_sync_mode(command, reactor, service)

            changes = self.api_flow(command)
            if not changes:
                self.log_failure(f'command could not parse flow in : {command}')
                await reactor.processes.answer_error_async(service)
                return

            # Register flush callbacks for connected peers (if sync mode)
            flush_events = register_flush_callbacks(peers, reactor, sync_mode)

            for change in changes:
                change.nlri.action = Action.ANNOUNCE
                reactor.configuration.inject_change(peers, change)
                peer_list = ', '.join(peers) if peers else 'all peers'
                self.log_message(f'flow added to {peer_list} : {change.extensive()}')
                await asyncio.sleep(0)  # Yield control after each flow (matches original yield False)

            # Wait for all peers to flush to wire (if sync mode)
            if flush_events:
                await asyncio.gather(*[e.wait() for e in flush_events])

            await reactor.processes.answer_done_async(service)
        except ValueError:
            self.log_failure('issue parsing the flow')
            await reactor.processes.answer_error_async(service)
        except IndexError:
            self.log_failure('issue parsing the flow')
            await reactor.processes.answer_error_async(service)

    reactor.asynchronous.schedule(service, line, callback())
    return True


@Command.register('withdraw flow', json_support=True)
def withdraw_flow(self: 'API', reactor: Reactor, service: str, line: str, use_json: bool) -> bool:
    async def callback() -> None:
        try:
            descriptions, command = extract_neighbors(line)
            peers = match_neighbors(reactor.peers(service), descriptions)
            if not peers:
                self.log_failure(f'no neighbor matching the command : {command}')
                await reactor.processes.answer_error_async(service)
                return

            # Parse sync mode and strip keywords
            command, sync_mode = parse_sync_mode(command, reactor, service)

            changes = self.api_flow(command)

            if not changes:
                self.log_failure(f'command could not parse flow in : {command}')
                await reactor.processes.answer_error_async(service)
                return

            # Register flush callbacks for connected peers (if sync mode)
            flush_events = register_flush_callbacks(peers, reactor, sync_mode)

            for change in changes:
                change.nlri.action = Action.WITHDRAW
                if reactor.configuration.inject_change(peers, change):
                    peer_list = ', '.join(peers) if peers else 'all peers'
                    self.log_message(f'flow removed from {peer_list} : {change.extensive()}')
                else:
                    peer_list = ', '.join(peers) if peers else 'all peers'
                    self.log_failure(f'flow not found on {peer_list} : {change.extensive()}')
                await asyncio.sleep(0)  # Yield control after each flow (matches original yield False)

            # Wait for all peers to flush to wire (if sync mode)
            if flush_events:
                await asyncio.gather(*[e.wait() for e in flush_events])

            await reactor.processes.answer_done_async(service)
        except ValueError:
            self.log_failure('issue parsing the flow')
            await reactor.processes.answer_error_async(service)
        except IndexError:
            self.log_failure('issue parsing the flow')
            await reactor.processes.answer_error_async(service)

    reactor.asynchronous.schedule(service, line, callback())
    return True


@Command.register('announce eor', json_support=True)
def announce_eor(self: 'API', reactor: 'Reactor', service: str, line: str, use_json: bool) -> bool:
    async def callback(self: 'API', command: str, peers: list[str]) -> None:
        result = self.api_eor(command)
        if not isinstance(result, Family):
            self.log_failure(f'Command could not parse eor : {command}')
            await reactor.processes.answer_error_async(service)
            return

        family: Family = result
        reactor.configuration.inject_eor(peers, family)
        peer_list = ', '.join(peers if peers else []) if peers is not None else 'all peers'
        self.log_message(f'Sent to {peer_list} : {family.extensive()}')
        await asyncio.sleep(0)  # Yield control (matches original yield False)

        await reactor.processes.answer_done_async(service)

    try:
        descriptions, command = extract_neighbors(line)
        peers = match_neighbors(reactor.established_peers(), descriptions)
        if not peers:
            self.log_failure('no neighbor matching the command : {}'.format(command))
            reactor.processes.answer_error(service)
            return False
        reactor.asynchronous.schedule(service, command, callback(self, command, peers))
        return True
    except ValueError:
        self.log_failure('issue parsing the command')
        reactor.processes.answer_error(service)
        return False
    except IndexError:
        self.log_failure('issue parsing the command')
        reactor.processes.answer_error(service)
        return False


@Command.register('announce route-refresh', json_support=True)
def announce_refresh(self: 'API', reactor: 'Reactor', service: str, line: str, use_json: bool) -> bool:
    async def callback(self: 'API', command: str, peers: list[str]) -> None:
        refreshes = self.api_refresh(command)
        if not refreshes:
            self.log_failure(f'Command could not parse route-refresh command : {command}')
            await reactor.processes.answer_error_async(service)
            return

        reactor.configuration.inject_refresh(peers, refreshes)
        for refresh in refreshes:
            peer_list = ', '.join(peers if peers else []) if peers is not None else 'all peers'
            self.log_message(f'Sent to {peer_list} : {refresh.extensive()}')

        await asyncio.sleep(0)  # Yield control (matches original yield False)
        await reactor.processes.answer_done_async(service)

    try:
        descriptions, command = extract_neighbors(line)
        peers = match_neighbors(reactor.established_peers(), descriptions)
        if not peers:
            self.log_failure('no neighbor matching the command : {}'.format(command))
            reactor.processes.answer_error(service)
            return False
        reactor.asynchronous.schedule(service, command, callback(self, command, peers))
        return True
    except ValueError:
        self.log_failure('issue parsing the command')
        reactor.processes.answer_error(service)
        return False
    except IndexError:
        self.log_failure('issue parsing the command')
        reactor.processes.answer_error(service)
        return False


@Command.register('announce operational', json_support=True)
def announce_operational(self: 'API', reactor: 'Reactor', service: str, line: str, use_json: bool) -> bool:
    async def callback(self: 'API', command: str, peers: list[str]) -> None:
        result = self.api_operational(command)
        if not result or result is True:
            self.log_failure(f'Command could not parse operational command : {command}')
            await reactor.processes.answer_error_async(service)
            return

        operational: Operational = result
        reactor.configuration.inject_operational(peers, operational)
        peer_list = ', '.join(peers if peers else []) if peers is not None else 'all peers'
        self.log_message(f'operational message sent to {peer_list} : {operational.extensive()}')
        await asyncio.sleep(0)  # Yield control (matches original yield False)
        await reactor.processes.answer_done_async(service)

    if (line.split() + ['be', 'safe'])[2].lower() not in (
        'asm',
        'adm',
        'rpcq',
        'rpcp',
        'apcq',
        'apcp',
        'lpcq',
        'lpcp',
    ):
        reactor.processes.answer_done(service)
        return False

    try:
        descriptions, command = extract_neighbors(line)
        peers = match_neighbors(reactor.peers(service), descriptions)
        if not peers:
            self.log_failure('no neighbor matching the command : {}'.format(command))
            reactor.processes.answer_error(service)
            return False
        reactor.asynchronous.schedule(service, command, callback(self, command, peers))
        return True
    except ValueError:
        self.log_failure('issue parsing the command')
        reactor.processes.answer_error(service)
        return False
    except IndexError:
        self.log_failure('issue parsing the command')
        reactor.processes.answer_error(service)
        return False


@Command.register('announce ipv4', json_support=True)
def announce_ipv4(self: 'API', reactor: Reactor, service: str, line: str, use_json: bool) -> bool:
    async def callback() -> None:
        try:
            descriptions, command = extract_neighbors(line)
            peers = match_neighbors(reactor.peers(service), descriptions)
            if not peers:
                self.log_failure(f'no neighbor matching the command : {command}')
                await reactor.processes.answer_error_async(service)
                return

            # Parse sync mode and strip keywords
            command, sync_mode = parse_sync_mode(command, reactor, service)

            changes = self.api_announce_v4(command)
            if not changes:
                self.log_failure(f'command could not parse ipv4 in : {command}')
                await reactor.processes.answer_error_async(service)
                return

            # Register flush callbacks for connected peers (if sync mode)
            flush_events = register_flush_callbacks(peers, reactor, sync_mode)

            for change in changes:
                change.nlri.action = Action.ANNOUNCE
                reactor.configuration.inject_change(peers, change)
                peer_list = ', '.join(peers) if peers else 'all peers'
                self.log_message(f'ipv4 added to {peer_list} : {change.extensive()}')
                await asyncio.sleep(0)  # Yield control after each route (matches original yield False)

            # Wait for all peers to flush to wire (if sync mode)
            if flush_events:
                await asyncio.gather(*[e.wait() for e in flush_events])

            await reactor.processes.answer_done_async(service)
        except ValueError:
            self.log_failure('issue parsing the ipv4')
            await reactor.processes.answer_error_async(service)
        except IndexError:
            self.log_failure('issue parsing the ipv4')
            await reactor.processes.answer_error_async(service)

    reactor.asynchronous.schedule(service, line, callback())
    return True


@Command.register('withdraw ipv4', json_support=True)
def withdraw_ipv4(self: 'API', reactor: Reactor, service: str, line: str, use_json: bool) -> bool:
    async def callback() -> None:
        try:
            descriptions, command = extract_neighbors(line)
            peers = match_neighbors(reactor.peers(service), descriptions)
            if not peers:
                self.log_failure(f'no neighbor matching the command : {command}')
                await reactor.processes.answer_error_async(service)
                return

            # Parse sync mode and strip keywords
            command, sync_mode = parse_sync_mode(command, reactor, service)

            changes = self.api_announce_v4(command)

            if not changes:
                self.log_failure(f'command could not parse ipv4 in : {command}')
                await reactor.processes.answer_error_async(service)
                return

            # Register flush callbacks for connected peers (if sync mode)
            flush_events = register_flush_callbacks(peers, reactor, sync_mode)

            for change in changes:
                change.nlri.action = Action.WITHDRAW
                if reactor.configuration.inject_change(peers, change):
                    peer_list = ', '.join(peers) if peers else 'all peers'
                    self.log_message(f'ipv4 removed from {peer_list} : {change.extensive()}')
                else:
                    peer_list = ', '.join(peers) if peers else 'all peers'
                    self.log_failure(f'ipv4 not found on {peer_list} : {change.extensive()}')
                await asyncio.sleep(0)  # Yield control after each route (matches original yield False)

            # Wait for all peers to flush to wire (if sync mode)
            if flush_events:
                await asyncio.gather(*[e.wait() for e in flush_events])

            await reactor.processes.answer_done_async(service)
        except ValueError:
            self.log_failure('issue parsing the ipv4')
            await reactor.processes.answer_error_async(service)
        except IndexError:
            self.log_failure('issue parsing the ipv4')
            await reactor.processes.answer_error_async(service)

    reactor.asynchronous.schedule(service, line, callback())
    return True


@Command.register('announce ipv6', json_support=True)
def announce_ipv6(self: 'API', reactor: Reactor, service: str, line: str, use_json: bool) -> bool:
    async def callback() -> None:
        try:
            descriptions, command = extract_neighbors(line)
            peers = match_neighbors(reactor.peers(service), descriptions)
            if not peers:
                self.log_failure(f'no neighbor matching the command : {command}')
                await reactor.processes.answer_error_async(service)
                return

            # Parse sync mode and strip keywords
            command, sync_mode = parse_sync_mode(command, reactor, service)

            changes = self.api_announce_v6(command)
            if not changes:
                self.log_failure(f'command could not parse ipv6 in : {command}')
                await reactor.processes.answer_error_async(service)
                return

            # Register flush callbacks for connected peers (if sync mode)
            flush_events = register_flush_callbacks(peers, reactor, sync_mode)

            for change in changes:
                change.nlri.action = Action.ANNOUNCE
                reactor.configuration.inject_change(peers, change)
                peer_list = ', '.join(peers) if peers else 'all peers'
                self.log_message(f'ipv6 added to {peer_list} : {change.extensive()}')
                await asyncio.sleep(0)  # Yield control after each route (matches original yield False)

            # Wait for all peers to flush to wire (if sync mode)
            if flush_events:
                await asyncio.gather(*[e.wait() for e in flush_events])

            await reactor.processes.answer_done_async(service)
        except ValueError:
            self.log_failure('issue parsing the ipv6')
            await reactor.processes.answer_error_async(service)
        except IndexError:
            self.log_failure('issue parsing the ipv6')
            await reactor.processes.answer_error_async(service)

    reactor.asynchronous.schedule(service, line, callback())
    return True


@Command.register('withdraw ipv6', json_support=True)
def withdraw_ipv6(self: 'API', reactor: Reactor, service: str, line: str, use_json: bool) -> bool:
    async def callback() -> None:
        try:
            descriptions, command = extract_neighbors(line)
            peers = match_neighbors(reactor.peers(service), descriptions)
            if not peers:
                self.log_failure(f'no neighbor matching the command : {command}')
                await reactor.processes.answer_error_async(service)
                return

            # Parse sync mode and strip keywords
            command, sync_mode = parse_sync_mode(command, reactor, service)

            changes = self.api_announce_v6(command)

            if not changes:
                self.log_failure(f'command could not parse ipv6 in : {command}')
                await reactor.processes.answer_error_async(service)
                return

            # Register flush callbacks for connected peers (if sync mode)
            flush_events = register_flush_callbacks(peers, reactor, sync_mode)

            for change in changes:
                change.nlri.action = Action.WITHDRAW
                if reactor.configuration.inject_change(peers, change):
                    peer_list = ', '.join(peers) if peers else 'all peers'
                    self.log_message(f'ipv6 removed from {peer_list} : {change.extensive()}')
                else:
                    peer_list = ', '.join(peers) if peers else 'all peers'
                    self.log_failure(f'ipv6 not found on {peer_list} : {change.extensive()}')
                await asyncio.sleep(0)  # Yield control after each route (matches original yield False)

            # Wait for all peers to flush to wire (if sync mode)
            if flush_events:
                await asyncio.gather(*[e.wait() for e in flush_events])

            await reactor.processes.answer_done_async(service)
        except ValueError:
            self.log_failure('issue parsing the ipv6')
            await reactor.processes.answer_error_async(service)
        except IndexError:
            self.log_failure('issue parsing the ipv6')
            await reactor.processes.answer_error_async(service)

    reactor.asynchronous.schedule(service, line, callback())
    return True
