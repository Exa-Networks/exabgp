"""line/watchdog.py

Created by Thomas Mangin on 2017-07-01.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import asyncio

from exabgp.reactor.api.command.command import Command
from exabgp.reactor.api.command.limit import match_neighbors
from exabgp.reactor.api.command.limit import extract_neighbors

from exabgp.protocol.ip import NoNextHop
from exabgp.bgp.message import Action
from exabgp.bgp.message.update.attribute import NextHop

from exabgp.configuration.static import ParseStaticRoute


def register_announce():
    pass


# @Command.register('debug')
# the command debug is hardcoded in the process code


@Command.register('announce route', json_support=True)
def announce_route(self, reactor, service, line, use_json):
    async def callback():
        try:
            descriptions, command = extract_neighbors(line)
            peers = match_neighbors(reactor.peers(service), descriptions)
            if not peers:
                error_msg = f'No neighbor matching the command: {command}'
                self.log_failure(error_msg)
                await reactor.processes.answer_error_async(service, error_msg)
                return

            # Strip trailing encoding keyword (json/text) that CLI appends
            # Example: "announce route 1.2.3.4/32 next-hop 2.4.5.6 json" -> "announce route 1.2.3.4/32 next-hop 2.4.5.6"
            command_parts = command.strip().split()
            if command_parts and command_parts[-1] in ('json', 'text'):
                command = ' '.join(command_parts[:-1])

            changes = self.api_route(command)
            if not changes:
                error_msg = f'Could not parse route: {command}'
                self.log_failure(error_msg)
                await reactor.processes.answer_error_async(service, error_msg)
                return

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
def withdraw_route(self, reactor, service, line, use_json):
    async def callback():
        try:
            descriptions, command = extract_neighbors(line)
            peers = match_neighbors(reactor.peers(service), descriptions)
            if not peers:
                error_msg = f'No neighbor matching the command: {command}'
                self.log_failure(error_msg)
                await reactor.processes.answer_error_async(service, error_msg)
                return

            # Strip trailing encoding keyword (json/text) that CLI appends
            # Example: "announce route 1.2.3.4/32 next-hop 2.4.5.6 json" -> "announce route 1.2.3.4/32 next-hop 2.4.5.6"
            command_parts = command.strip().split()
            if command_parts and command_parts[-1] in ('json', 'text'):
                command = ' '.join(command_parts[:-1])

            changes = self.api_route(command)
            if not changes:
                error_msg = f'Could not parse route: {command}'
                self.log_failure(error_msg)
                await reactor.processes.answer_error_async(service, error_msg)
                return

            for change in changes:
                # Change the action to withdraw before checking the route
                change.nlri.action = Action.WITHDRAW
                # NextHop is a mandatory field (but we do not require in)
                if change.nlri.nexthop is NoNextHop:
                    change.nlri.nexthop = NextHop('0.0.0.0')

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
def announce_vpls(self, reactor, service, line, use_json):
    async def callback():
        try:
            descriptions, command = extract_neighbors(line)
            peers = match_neighbors(reactor.peers(service), descriptions)
            if not peers:
                self.log_failure(f'no neighbor matching the command : {command}')
                await reactor.processes.answer_error_async(service)
                return

            changes = self.api_vpls(command)
            if not changes:
                self.log_failure(f'command could not parse vpls in : {command}')
                await reactor.processes.answer_error_async(service)
                return

            for change in changes:
                change.nlri.action = Action.ANNOUNCE
                reactor.configuration.inject_change(peers, change)
                peer_list = ', '.join(peers) if peers else 'all peers'
                self.log_message(f'vpls added to {peer_list} : {change.extensive()}')
                await asyncio.sleep(0)  # Yield control after each route (matches original yield False)

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
def withdraw_vpls(self, reactor, service, line, use_json):
    async def callback():
        try:
            descriptions, command = extract_neighbors(line)
            peers = match_neighbors(reactor.peers(service), descriptions)
            if not peers:
                self.log_failure(f'no neighbor matching the command : {command}')
                await reactor.processes.answer_error_async(service)
                return

            changes = self.api_vpls(command)

            if not changes:
                self.log_failure(f'command could not parse vpls in : {command}')
                await reactor.processes.answer_error_async(service)
                return

            for change in changes:
                change.nlri.action = Action.WITHDRAW
                if reactor.configuration.inject_change(peers, change):
                    peer_list = ', '.join(peers) if peers else 'all peers'
                    self.log_message(f'vpls removed from {peer_list} : {change.extensive()}')
                else:
                    peer_list = ', '.join(peers) if peers else 'all peers'
                    self.log_failure(f'vpls not found on {peer_list} : {change.extensive()}')
                await asyncio.sleep(0)  # Yield control after each route (matches original yield False in both branches)

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
def announce_attributes(self, reactor, service, line, use_json):
    async def callback():
        try:
            descriptions, command = extract_neighbors(line)
            peers = match_neighbors(reactor.peers(service), descriptions)
            if not peers:
                self.log_failure(f'no neighbor matching the command : {command}')
                await reactor.processes.answer_error_async(service)
                return

            changes = self.api_attributes(command, peers)
            if not changes:
                self.log_failure(f'command could not parse route in : {command}')
                await reactor.processes.answer_error_async(service)
                return

            for change in changes:
                change.nlri.action = Action.ANNOUNCE
                reactor.configuration.inject_change(peers, change)
                peer_list = ', '.join(peers) if peers else 'all peers'
                self.log_message(f'route added to {peer_list} : {change.extensive()}')
                await asyncio.sleep(0)  # Yield control after each route (matches original yield False)

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
def withdraw_attribute(self, reactor, service, line, use_json):
    async def callback():
        try:
            descriptions, command = extract_neighbors(line)
            peers = match_neighbors(reactor.peers(service), descriptions)
            if not peers:
                self.log_failure(f'no neighbor matching the command : {command}')
                await reactor.processes.answer_error_async(service)
                return

            changes = self.api_attributes(command, peers)
            if not changes:
                self.log_failure(f'command could not parse route in : {command}')
                await reactor.processes.answer_error_async(service)
                return

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
def announce_flow(self, reactor, service, line, use_json):
    async def callback():
        try:
            descriptions, command = extract_neighbors(line)
            peers = match_neighbors(reactor.peers(service), descriptions)
            if not peers:
                self.log_failure(f'no neighbor matching the command : {command}')
                await reactor.processes.answer_error_async(service)
                return

            changes = self.api_flow(command)
            if not changes:
                self.log_failure(f'command could not parse flow in : {command}')
                await reactor.processes.answer_error_async(service)
                return

            for change in changes:
                change.nlri.action = Action.ANNOUNCE
                reactor.configuration.inject_change(peers, change)
                peer_list = ', '.join(peers) if peers else 'all peers'
                self.log_message(f'flow added to {peer_list} : {change.extensive()}')
                await asyncio.sleep(0)  # Yield control after each flow (matches original yield False)

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
def withdraw_flow(self, reactor, service, line, use_json):
    async def callback():
        try:
            descriptions, command = extract_neighbors(line)
            peers = match_neighbors(reactor.peers(service), descriptions)
            if not peers:
                self.log_failure(f'no neighbor matching the command : {command}')
                await reactor.processes.answer_error_async(service)
                return

            changes = self.api_flow(command)

            if not changes:
                self.log_failure(f'command could not parse flow in : {command}')
                await reactor.processes.answer_error_async(service)
                return

            for change in changes:
                change.nlri.action = Action.WITHDRAW
                if reactor.configuration.inject_change(peers, change):
                    peer_list = ', '.join(peers) if peers else 'all peers'
                    self.log_message(f'flow removed from {peer_list} : {change.extensive()}')
                else:
                    peer_list = ', '.join(peers) if peers else 'all peers'
                    self.log_failure(f'flow not found on {peer_list} : {change.extensive()}')
                await asyncio.sleep(0)  # Yield control after each flow (matches original yield False)

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
def announce_eor(self, reactor, service, line, use_json):
    async def callback(self, command, peers):
        family = self.api_eor(command)
        if not family:
            self.log_failure(f'Command could not parse eor : {command}')
            await reactor.processes.answer_error_async(service)
            return

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
def announce_refresh(self, reactor, service, line, use_json):
    async def callback(self, command, peers):
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
def announce_operational(self, reactor, service, line, use_json):
    async def callback(self, command, peers):
        operational = self.api_operational(command)
        if not operational:
            self.log_failure(f'Command could not parse operational command : {command}')
            await reactor.processes.answer_error_async(service)
            return

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
def announce_ipv4(self, reactor, service, line, use_json):
    async def callback():
        try:
            descriptions, command = extract_neighbors(line)
            peers = match_neighbors(reactor.peers(service), descriptions)
            if not peers:
                self.log_failure(f'no neighbor matching the command : {command}')
                await reactor.processes.answer_error_async(service)
                return

            changes = self.api_announce_v4(command)
            if not changes:
                self.log_failure(f'command could not parse ipv4 in : {command}')
                await reactor.processes.answer_error_async(service)
                return

            for change in changes:
                change.nlri.action = Action.ANNOUNCE
                reactor.configuration.inject_change(peers, change)
                peer_list = ', '.join(peers) if peers else 'all peers'
                self.log_message(f'ipv4 added to {peer_list} : {change.extensive()}')
                await asyncio.sleep(0)  # Yield control after each route (matches original yield False)

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
def withdraw_ipv4(self, reactor, service, line, use_json):
    async def callback():
        try:
            descriptions, command = extract_neighbors(line)
            peers = match_neighbors(reactor.peers(service), descriptions)
            if not peers:
                self.log_failure(f'no neighbor matching the command : {command}')
                await reactor.processes.answer_error_async(service)
                return

            changes = self.api_announce_v4(command)

            if not changes:
                self.log_failure(f'command could not parse ipv4 in : {command}')
                await reactor.processes.answer_error_async(service)
                return

            for change in changes:
                change.nlri.action = Action.WITHDRAW
                if reactor.configuration.inject_change(peers, change):
                    peer_list = ', '.join(peers) if peers else 'all peers'
                    self.log_message(f'ipv4 removed from {peer_list} : {change.extensive()}')
                else:
                    peer_list = ', '.join(peers) if peers else 'all peers'
                    self.log_failure(f'ipv4 not found on {peer_list} : {change.extensive()}')
                await asyncio.sleep(0)  # Yield control after each route (matches original yield False)

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
def announce_ipv6(self, reactor, service, line, use_json):
    async def callback():
        try:
            descriptions, command = extract_neighbors(line)
            peers = match_neighbors(reactor.peers(service), descriptions)
            if not peers:
                self.log_failure(f'no neighbor matching the command : {command}')
                await reactor.processes.answer_error_async(service)
                return

            changes = self.api_announce_v6(command)
            if not changes:
                self.log_failure(f'command could not parse ipv6 in : {command}')
                await reactor.processes.answer_error_async(service)
                return

            for change in changes:
                change.nlri.action = Action.ANNOUNCE
                reactor.configuration.inject_change(peers, change)
                peer_list = ', '.join(peers) if peers else 'all peers'
                self.log_message(f'ipv6 added to {peer_list} : {change.extensive()}')
                await asyncio.sleep(0)  # Yield control after each route (matches original yield False)

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
def withdraw_ipv6(self, reactor, service, line, use_json):
    async def callback():
        try:
            descriptions, command = extract_neighbors(line)
            peers = match_neighbors(reactor.peers(service), descriptions)
            if not peers:
                self.log_failure(f'no neighbor matching the command : {command}')
                await reactor.processes.answer_error_async(service)
                return

            changes = self.api_announce_v6(command)

            if not changes:
                self.log_failure(f'command could not parse ipv6 in : {command}')
                await reactor.processes.answer_error_async(service)
                return

            for change in changes:
                change.nlri.action = Action.WITHDRAW
                if reactor.configuration.inject_change(peers, change):
                    peer_list = ', '.join(peers) if peers else 'all peers'
                    self.log_message(f'ipv6 removed from {peer_list} : {change.extensive()}')
                else:
                    peer_list = ', '.join(peers) if peers else 'all peers'
                    self.log_failure(f'ipv6 not found on {peer_list} : {change.extensive()}')
                await asyncio.sleep(0)  # Yield control after each route (matches original yield False)

            await reactor.processes.answer_done_async(service)
        except ValueError:
            self.log_failure('issue parsing the ipv6')
            await reactor.processes.answer_error_async(service)
        except IndexError:
            self.log_failure('issue parsing the ipv6')
            await reactor.processes.answer_error_async(service)

    reactor.asynchronous.schedule(service, line, callback())
    return True
