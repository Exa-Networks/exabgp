"""command/announce.py

Route announcement and withdrawal commands.

Created by Thomas Mangin on 2017-07-01.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from exabgp.protocol.ip import IP
from exabgp.protocol.family import Family
from exabgp.bgp.message.update.attribute import NextHop
from exabgp.bgp.message.update.collection import validate_announce_nlri

from exabgp.logger import log, lazymsg

if TYPE_CHECKING:
    from exabgp.rib.route import Route
    from exabgp.reactor.api import API
    from exabgp.reactor.loop import Reactor


def register_announce() -> None:
    pass


def validate_announce(route: 'Route') -> str | None:
    """Validate route for announcement, return error message or None if valid.

    Provides early validation at API level for immediate feedback.
    Uses shared validation logic from collection.py.
    """
    return validate_announce_nlri(route.nlri, route.nexthop)


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


def announce_route(
    self: 'API', reactor: 'Reactor', service: str, peers: list[str], command: str, use_json: bool, action: str = ''
) -> bool:
    async def callback() -> None:
        try:
            # Parse sync mode and strip keywords
            cmd, sync_mode = parse_sync_mode(command, reactor, service)

            routes = self.api_route(cmd, action)
            if not routes:
                error_msg = f'Could not parse route: {cmd}'
                self.log_failure(error_msg)
                await reactor.processes.answer_error_async(service, error_msg)
                return

            # Register flush callbacks for connected peers (if sync mode)
            flush_events = register_flush_callbacks(peers, reactor, sync_mode)

            for route in routes:
                # Validate route before announcing (early feedback)
                error = validate_announce(route)
                if error:
                    peer_list = ', '.join(peers) if peers else 'all peers'
                    self.log_failure(f'invalid route for {peer_list}: {error}')
                    await reactor.processes.answer_error_async(service, error)
                    return

                reactor.configuration.announce_route(peers, route)
                peer_list = ', '.join(peers) if peers else 'all peers'
                self.log_message(f'route added to {peer_list} : {route.extensive()}')
                await asyncio.sleep(0)

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
            self.log_exception(error_msg, e)
            await reactor.processes.answer_error_async(service, error_msg)

    reactor.asynchronous.schedule(service, command, callback())
    return True


def withdraw_route(
    self: 'API', reactor: 'Reactor', service: str, peers: list[str], command: str, use_json: bool, action: str = ''
) -> bool:
    async def callback() -> None:
        try:
            # Parse sync mode and strip keywords
            cmd, sync_mode = parse_sync_mode(command, reactor, service)

            routes = self.api_route(cmd, action)
            if not routes:
                error_msg = f'Could not parse route: {cmd}'
                self.log_failure(error_msg)
                await reactor.processes.answer_error_async(service, error_msg)
                return

            # Register flush callbacks for connected peers (if sync mode)
            flush_events = register_flush_callbacks(peers, reactor, sync_mode)

            for route in routes:
                # NextHop is a mandatory field (but we do not require it for withdraws)
                if route.nexthop is IP.NoNextHop:
                    route = route.with_nexthop(NextHop.from_string('0.0.0.0'))

                if reactor.configuration.withdraw_route(peers, route):
                    peer_list = ', '.join(peers) if peers else 'all peers'
                    self.log_message(f'route removed from {peer_list} : {route.extensive()}')
                else:
                    peer_list = ', '.join(peers) if peers else 'all peers'
                    self.log_failure(f'route not found on {peer_list} : {route.extensive()}')
                await asyncio.sleep(0)

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
            self.log_exception(error_msg, e)
            await reactor.processes.answer_error_async(service, error_msg)

    reactor.asynchronous.schedule(service, command, callback())
    return True


def announce_vpls(
    self: 'API', reactor: 'Reactor', service: str, peers: list[str], command: str, use_json: bool, action: str = ''
) -> bool:
    async def callback() -> None:
        try:
            # Parse sync mode and strip keywords
            cmd, sync_mode = parse_sync_mode(command, reactor, service)

            routes = self.api_vpls(cmd, action)
            if not routes:
                self.log_failure(f'command could not parse vpls in : {cmd}')
                await reactor.processes.answer_error_async(service)
                return

            # Register flush callbacks for connected peers (if sync mode)
            flush_events = register_flush_callbacks(peers, reactor, sync_mode)

            for route in routes:
                reactor.configuration.announce_route(peers, route)
                peer_list = ', '.join(peers) if peers else 'all peers'
                self.log_message(f'vpls added to {peer_list} : {route.extensive()}')
                await asyncio.sleep(0)

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

    reactor.asynchronous.schedule(service, command, callback())
    return True


def withdraw_vpls(
    self: 'API', reactor: 'Reactor', service: str, peers: list[str], command: str, use_json: bool, action: str = ''
) -> bool:
    async def callback() -> None:
        try:
            # Parse sync mode and strip keywords
            cmd, sync_mode = parse_sync_mode(command, reactor, service)

            routes = self.api_vpls(cmd, action)

            if not routes:
                self.log_failure(f'command could not parse vpls in : {cmd}')
                await reactor.processes.answer_error_async(service)
                return

            # Register flush callbacks for connected peers (if sync mode)
            flush_events = register_flush_callbacks(peers, reactor, sync_mode)

            for route in routes:
                if reactor.configuration.withdraw_route(peers, route):
                    peer_list = ', '.join(peers) if peers else 'all peers'
                    self.log_message(f'vpls removed from {peer_list} : {route.extensive()}')
                else:
                    peer_list = ', '.join(peers) if peers else 'all peers'
                    self.log_failure(f'vpls not found on {peer_list} : {route.extensive()}')
                await asyncio.sleep(0)

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

    reactor.asynchronous.schedule(service, command, callback())
    return True


def announce_attributes(
    self: 'API', reactor: 'Reactor', service: str, peers: list[str], command: str, use_json: bool, action: str = ''
) -> bool:
    async def callback() -> None:
        try:
            # Parse sync mode and strip keywords
            cmd, sync_mode = parse_sync_mode(command, reactor, service)

            routes = self.api_attributes(cmd, peers, action)
            if not routes:
                self.log_failure(f'command could not parse route in : {cmd}')
                await reactor.processes.answer_error_async(service)
                return

            # Register flush callbacks for connected peers (if sync mode)
            flush_events = register_flush_callbacks(peers, reactor, sync_mode)

            for route in routes:
                reactor.configuration.announce_route(peers, route)
                peer_list = ', '.join(peers) if peers else 'all peers'
                self.log_message(f'route added to {peer_list} : {route.extensive()}')
                await asyncio.sleep(0)

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
            self.log_exception(error_msg, e)
            await reactor.processes.answer_error_async(service, error_msg)

    reactor.asynchronous.schedule(service, command, callback())
    return True


def withdraw_attribute(
    self: 'API', reactor: 'Reactor', service: str, peers: list[str], command: str, use_json: bool, action: str = ''
) -> bool:
    async def callback() -> None:
        try:
            # Parse sync mode and strip keywords
            cmd, sync_mode = parse_sync_mode(command, reactor, service)

            routes = self.api_attributes(cmd, peers, action)
            if not routes:
                self.log_failure(f'command could not parse route in : {cmd}')
                await reactor.processes.answer_error_async(service)
                return

            # Register flush callbacks for connected peers (if sync mode)
            flush_events = register_flush_callbacks(peers, reactor, sync_mode)

            for route in routes:
                if reactor.configuration.withdraw_route(peers, route):
                    peer_list = ', '.join(peers) if peers else 'all peers'
                    self.log_message(f'route removed from {peer_list} : {route.extensive()}')
                    await asyncio.sleep(0)
                else:
                    peer_list = ', '.join(peers) if peers else 'all peers'
                    self.log_failure(f'route not found on {peer_list} : {route.extensive()}')
                    await asyncio.sleep(0)

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
            self.log_exception(error_msg, e)
            await reactor.processes.answer_error_async(service, error_msg)

    reactor.asynchronous.schedule(service, command, callback())
    return True


def announce_flow(
    self: 'API', reactor: 'Reactor', service: str, peers: list[str], command: str, use_json: bool, action: str = ''
) -> bool:
    async def callback() -> None:
        try:
            # Parse sync mode and strip keywords
            cmd, sync_mode = parse_sync_mode(command, reactor, service)

            routes = self.api_flow(cmd, action)
            if not routes:
                self.log_failure(f'command could not parse flow in : {cmd}')
                await reactor.processes.answer_error_async(service)
                return

            # Register flush callbacks for connected peers (if sync mode)
            flush_events = register_flush_callbacks(peers, reactor, sync_mode)

            for route in routes:
                reactor.configuration.announce_route(peers, route)
                peer_list = ', '.join(peers) if peers else 'all peers'
                self.log_message(f'flow added to {peer_list} : {route.extensive()}')
                await asyncio.sleep(0)

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

    reactor.asynchronous.schedule(service, command, callback())
    return True


def withdraw_flow(
    self: 'API', reactor: 'Reactor', service: str, peers: list[str], command: str, use_json: bool, action: str = ''
) -> bool:
    async def callback() -> None:
        try:
            # Parse sync mode and strip keywords
            cmd, sync_mode = parse_sync_mode(command, reactor, service)

            routes = self.api_flow(cmd, action)

            if not routes:
                self.log_failure(f'command could not parse flow in : {cmd}')
                await reactor.processes.answer_error_async(service)
                return

            # Register flush callbacks for connected peers (if sync mode)
            flush_events = register_flush_callbacks(peers, reactor, sync_mode)

            for route in routes:
                if reactor.configuration.withdraw_route(peers, route):
                    peer_list = ', '.join(peers) if peers else 'all peers'
                    self.log_message(f'flow removed from {peer_list} : {route.extensive()}')
                else:
                    peer_list = ', '.join(peers) if peers else 'all peers'
                    self.log_failure(f'flow not found on {peer_list} : {route.extensive()}')
                await asyncio.sleep(0)

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

    reactor.asynchronous.schedule(service, command, callback())
    return True


def announce_eor(
    self: 'API', reactor: 'Reactor', service: str, peers: list[str], command: str, use_json: bool, action: str = ''
) -> bool:
    async def callback() -> None:
        # EOR requires established peers to send to
        established = set(reactor.established_peers())
        active_peers = [p for p in peers if p in established]
        if not active_peers:
            self.log_failure('No established peers to send EOR to')
            await reactor.processes.answer_error_async(service)
            return

        result = self.api_eor(command, action)
        if not isinstance(result, Family):
            self.log_failure(f'Command could not parse eor : {command}')
            await reactor.processes.answer_error_async(service)
            return

        family: Family = result
        reactor.configuration.inject_eor(active_peers, family)
        peer_list = ', '.join(active_peers)
        self.log_message(f'Sent to {peer_list} : {family.extensive()}')
        await asyncio.sleep(0)

        await reactor.processes.answer_done_async(service)

    try:
        reactor.asynchronous.schedule(service, command, callback())
        return True
    except ValueError:
        self.log_failure('issue parsing the command')
        reactor.processes.answer_error(service)
        return False
    except IndexError:
        self.log_failure('issue parsing the command')
        reactor.processes.answer_error(service)
        return False


def announce_refresh(
    self: 'API', reactor: 'Reactor', service: str, peers: list[str], command: str, use_json: bool, action: str = ''
) -> bool:
    async def callback() -> None:
        # Route-refresh requires established peers to send to
        established = set(reactor.established_peers())
        active_peers = [p for p in peers if p in established]
        if not active_peers:
            self.log_failure('No established peers to send route-refresh to')
            await reactor.processes.answer_error_async(service)
            return

        refreshes = self.api_refresh(command, action)
        if not refreshes:
            self.log_failure(f'Command could not parse route-refresh command : {command}')
            await reactor.processes.answer_error_async(service)
            return

        reactor.configuration.inject_refresh(active_peers, refreshes)
        for refresh in refreshes:
            peer_list = ', '.join(active_peers)
            self.log_message(f'Sent to {peer_list} : {refresh.extensive()}')

        await asyncio.sleep(0)
        await reactor.processes.answer_done_async(service)

    try:
        reactor.asynchronous.schedule(service, command, callback())
        return True
    except ValueError:
        self.log_failure('issue parsing the command')
        reactor.processes.answer_error(service)
        return False
    except IndexError:
        self.log_failure('issue parsing the command')
        reactor.processes.answer_error(service)
        return False


def announce_operational(
    self: 'API', reactor: 'Reactor', service: str, peers: list[str], command: str, use_json: bool, action: str = ''
) -> bool:
    from exabgp.bgp.message.operational import Operational

    async def callback() -> None:
        result = self.api_operational(command, action)
        if not result or result is True:
            self.log_failure(f'Command could not parse operational command : {command}')
            await reactor.processes.answer_error_async(service)
            return

        operational: Operational = result
        reactor.configuration.inject_operational(peers, operational)
        peer_list = ', '.join(peers) if peers else 'all peers'
        self.log_message(f'operational message sent to {peer_list} : {operational.extensive()}')
        await asyncio.sleep(0)
        await reactor.processes.answer_done_async(service)

    # Check for valid operational subcommand
    words = command.split() + ['be', 'safe']
    if len(words) >= 2 and words[1].lower() not in (
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
        reactor.asynchronous.schedule(service, command, callback())
        return True
    except ValueError:
        self.log_failure('issue parsing the command')
        reactor.processes.answer_error(service)
        return False
    except IndexError:
        self.log_failure('issue parsing the command')
        reactor.processes.answer_error(service)
        return False


def announce_ipv4(
    self: 'API', reactor: 'Reactor', service: str, peers: list[str], command: str, use_json: bool, action: str = ''
) -> bool:
    async def callback() -> None:
        try:
            # Parse sync mode and strip keywords
            cmd, sync_mode = parse_sync_mode(command, reactor, service)

            routes = self.api_announce_v4(cmd, action)
            if not routes:
                self.log_failure(f'command could not parse ipv4 in : {cmd}')
                await reactor.processes.answer_error_async(service)
                return

            # Register flush callbacks for connected peers (if sync mode)
            flush_events = register_flush_callbacks(peers, reactor, sync_mode)

            for route in routes:
                reactor.configuration.announce_route(peers, route)
                peer_list = ', '.join(peers) if peers else 'all peers'
                self.log_message(f'ipv4 added to {peer_list} : {route.extensive()}')
                await asyncio.sleep(0)

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

    reactor.asynchronous.schedule(service, command, callback())
    return True


def withdraw_ipv4(
    self: 'API', reactor: 'Reactor', service: str, peers: list[str], command: str, use_json: bool, action: str = ''
) -> bool:
    async def callback() -> None:
        try:
            # Parse sync mode and strip keywords
            cmd, sync_mode = parse_sync_mode(command, reactor, service)

            routes = self.api_announce_v4(cmd, action)

            if not routes:
                self.log_failure(f'command could not parse ipv4 in : {cmd}')
                await reactor.processes.answer_error_async(service)
                return

            # Register flush callbacks for connected peers (if sync mode)
            flush_events = register_flush_callbacks(peers, reactor, sync_mode)

            for route in routes:
                if reactor.configuration.withdraw_route(peers, route):
                    peer_list = ', '.join(peers) if peers else 'all peers'
                    self.log_message(f'ipv4 removed from {peer_list} : {route.extensive()}')
                else:
                    peer_list = ', '.join(peers) if peers else 'all peers'
                    self.log_failure(f'ipv4 not found on {peer_list} : {route.extensive()}')
                await asyncio.sleep(0)

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

    reactor.asynchronous.schedule(service, command, callback())
    return True


def announce_ipv6(
    self: 'API', reactor: 'Reactor', service: str, peers: list[str], command: str, use_json: bool, action: str = ''
) -> bool:
    async def callback() -> None:
        try:
            # Parse sync mode and strip keywords
            cmd, sync_mode = parse_sync_mode(command, reactor, service)

            routes = self.api_announce_v6(cmd, action)
            if not routes:
                self.log_failure(f'command could not parse ipv6 in : {cmd}')
                await reactor.processes.answer_error_async(service)
                return

            # Register flush callbacks for connected peers (if sync mode)
            flush_events = register_flush_callbacks(peers, reactor, sync_mode)

            for route in routes:
                reactor.configuration.announce_route(peers, route)
                peer_list = ', '.join(peers) if peers else 'all peers'
                self.log_message(f'ipv6 added to {peer_list} : {route.extensive()}')
                await asyncio.sleep(0)

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

    reactor.asynchronous.schedule(service, command, callback())
    return True


def withdraw_ipv6(
    self: 'API', reactor: 'Reactor', service: str, peers: list[str], command: str, use_json: bool, action: str = ''
) -> bool:
    async def callback() -> None:
        try:
            # Parse sync mode and strip keywords
            cmd, sync_mode = parse_sync_mode(command, reactor, service)

            routes = self.api_announce_v6(cmd, action)

            if not routes:
                self.log_failure(f'command could not parse ipv6 in : {cmd}')
                await reactor.processes.answer_error_async(service)
                return

            # Register flush callbacks for connected peers (if sync mode)
            flush_events = register_flush_callbacks(peers, reactor, sync_mode)

            for route in routes:
                if reactor.configuration.withdraw_route(peers, route):
                    peer_list = ', '.join(peers) if peers else 'all peers'
                    self.log_message(f'ipv6 removed from {peer_list} : {route.extensive()}')
                else:
                    peer_list = ', '.join(peers) if peers else 'all peers'
                    self.log_failure(f'ipv6 not found on {peer_list} : {route.extensive()}')
                await asyncio.sleep(0)

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

    reactor.asynchronous.schedule(service, command, callback())
    return True


# =============================================================================
# v6 announce/withdraw dispatcher functions
# =============================================================================

# v6 announce dispatcher mapping
_V6_ANNOUNCE_HANDLERS: dict[str, str] = {
    'route': 'announce_route',
    'route-refresh': 'announce_refresh',
    'ipv4': 'announce_ipv4',
    'ipv6': 'announce_ipv6',
    'flow': 'announce_flow',
    'eor': 'announce_eor',
    'watchdog': 'announce_watchdog',
    'attribute': 'announce_attributes',
    'attributes': 'announce_attributes',
    'operational': 'announce_operational',
    'vpls': 'announce_vpls',
}

# v6 withdraw dispatcher mapping
_V6_WITHDRAW_HANDLERS: dict[str, str] = {
    'route': 'withdraw_route',
    'ipv4': 'withdraw_ipv4',
    'ipv6': 'withdraw_ipv6',
    'flow': 'withdraw_flow',
    'watchdog': 'withdraw_watchdog',
    'attribute': 'withdraw_attribute',
    'attributes': 'withdraw_attribute',
    'vpls': 'withdraw_vpls',
}


def v6_announce(self: 'API', reactor: 'Reactor', service: str, peers: list[str], command: str, use_json: bool) -> bool:
    """v6 announce dispatcher - routes to specific handler based on type token.

    Command format: <type> <spec>
    e.g., "route 10.0.0.0/24 next-hop 1.2.3.4"

    Passes action='announce' to handlers for clean format parsing in api_* methods.
    """
    from exabgp.reactor.api.command import watchdog as watchdog_cmd

    words = command.split(None, 1)
    if not words:
        reactor.processes.answer_error(service)
        return False

    route_type = words[0]
    handler_name = _V6_ANNOUNCE_HANDLERS.get(route_type)
    if not handler_name:
        reactor.processes.answer_error(service, f'unknown announce type: {route_type}')
        return False

    # Get handler from this module or watchdog module
    if 'watchdog' in handler_name:
        handler = getattr(watchdog_cmd, handler_name)
    else:
        handler = globals()[handler_name]

    # Pass action='announce' for clean format parsing
    return bool(handler(self, reactor, service, peers, command, use_json, action='announce'))


def v6_withdraw(self: 'API', reactor: 'Reactor', service: str, peers: list[str], command: str, use_json: bool) -> bool:
    """v6 withdraw dispatcher - routes to specific handler based on type token.

    Command format: <type> <spec>
    e.g., "route 10.0.0.0/24"

    Passes action='withdraw' to handlers for clean format parsing in api_* methods.
    """
    from exabgp.reactor.api.command import watchdog as watchdog_cmd

    words = command.split(None, 1)
    if not words:
        reactor.processes.answer_error(service)
        return False

    route_type = words[0]
    handler_name = _V6_WITHDRAW_HANDLERS.get(route_type)
    if not handler_name:
        reactor.processes.answer_error(service, f'unknown withdraw type: {route_type}')
        return False

    # Get handler from this module or watchdog module
    if 'watchdog' in handler_name:
        handler = getattr(watchdog_cmd, handler_name)
    else:
        handler = globals()[handler_name]

    # Pass action='withdraw' for clean format parsing
    return bool(handler(self, reactor, service, peers, command, use_json, action='withdraw'))
