"""line/watchdog.py

Created by Thomas Mangin on 2017-07-01.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

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


@Command.register('announce route')
def announce_route(self, reactor, service, line, use_json):
    def callback():
        try:
            descriptions, command = extract_neighbors(line)
            peers = match_neighbors(reactor.peers(service), descriptions)
            if not peers:
                self.log_failure(f'no neighbor matching the command : {command}')
                reactor.processes.answer_error(service)
                yield True
                return

            changes = self.api_route(command)
            if not changes:
                self.log_failure(f'command could not parse route in : {command}')
                reactor.processes.answer_error(service)
                yield True
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
                yield False

            reactor.processes.answer_done(service)
        except ValueError:
            self.log_failure('issue parsing the route')
            reactor.processes.answer_error(service)
            yield True
        except IndexError:
            self.log_failure('issue parsing the route')
            reactor.processes.answer_error(service)
            yield True

    reactor.asynchronous.schedule(service, line, callback())
    return True


@Command.register('withdraw route')
def withdraw_route(self, reactor, service, line, use_json):
    def callback():
        try:
            descriptions, command = extract_neighbors(line)
            peers = match_neighbors(reactor.peers(service), descriptions)
            if not peers:
                self.log_failure(f'no neighbor matching the command : {command}')
                reactor.processes.answer_error(service)
                yield True
                return

            changes = self.api_route(command)
            if not changes:
                self.log_failure(f'command could not parse route in : {command}')
                reactor.processes.answer_error(service)
                yield True
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
                    yield False
                else:
                    peer_list = ', '.join(peers) if peers else 'all peers'
                    self.log_failure(f'route not found on {peer_list} : {change.extensive()}')
                    yield False

            reactor.processes.answer_done(service)
        except ValueError:
            self.log_failure('issue parsing the route')
            reactor.processes.answer_error(service)
            yield True
        except IndexError:
            self.log_failure('issue parsing the route')
            reactor.processes.answer_error(service)
            yield True

    reactor.asynchronous.schedule(service, line, callback())
    return True


@Command.register('announce vpls')
def announce_vpls(self, reactor, service, line, use_json):
    def callback():
        try:
            descriptions, command = extract_neighbors(line)
            peers = match_neighbors(reactor.peers(service), descriptions)
            if not peers:
                self.log_failure(f'no neighbor matching the command : {command}')
                reactor.processes.answer_error(service)
                yield True
                return

            changes = self.api_vpls(command)
            if not changes:
                self.log_failure(f'command could not parse vpls in : {command}')
                reactor.processes.answer_error(service)
                yield True
                return

            for change in changes:
                change.nlri.action = Action.ANNOUNCE
                reactor.configuration.inject_change(peers, change)
                peer_list = ', '.join(peers) if peers else 'all peers'
                self.log_message(f'vpls added to {peer_list} : {change.extensive()}')
                yield False

            reactor.processes.answer_done(service)
        except ValueError:
            self.log_failure('issue parsing the vpls')
            reactor.processes.answer_error(service)
            yield True
        except IndexError:
            self.log_failure('issue parsing the vpls')
            reactor.processes.answer_error(service)
            yield True

    reactor.asynchronous.schedule(service, line, callback())
    return True


@Command.register('withdraw vpls')
def withdraw_vpls(self, reactor, service, line, use_json):
    def callback():
        try:
            descriptions, command = extract_neighbors(line)
            peers = match_neighbors(reactor.peers(service), descriptions)
            if not peers:
                self.log_failure(f'no neighbor matching the command : {command}')
                reactor.processes.answer_error(service)
                yield True
                return

            changes = self.api_vpls(command)

            if not changes:
                self.log_failure(f'command could not parse vpls in : {command}')
                reactor.processes.answer_error(service)
                yield True
                return

            for change in changes:
                change.nlri.action = Action.WITHDRAW
                if reactor.configuration.inject_change(peers, change):
                    peer_list = ', '.join(peers) if peers else 'all peers'
                    self.log_message(f'vpls removed from {peer_list} : {change.extensive()}')
                    yield False
                else:
                    peer_list = ', '.join(peers) if peers else 'all peers'
                    self.log_failure(f'vpls not found on {peer_list} : {change.extensive()}')
                    yield False

            reactor.processes.answer_done(service)
        except ValueError:
            self.log_failure('issue parsing the vpls')
            reactor.processes.answer_error(service)
            yield True
        except IndexError:
            self.log_failure('issue parsing the vpls')
            reactor.processes.answer_error(service)
            yield True

    reactor.asynchronous.schedule(service, line, callback())
    return True


@Command.register('announce attribute')
@Command.register('announce attributes')
def announce_attributes(self, reactor, service, line, use_json):
    def callback():
        try:
            descriptions, command = extract_neighbors(line)
            peers = match_neighbors(reactor.peers(service), descriptions)
            if not peers:
                self.log_failure(f'no neighbor matching the command : {command}')
                reactor.processes.answer_error(service)
                yield True
                return

            changes = self.api_attributes(command, peers)
            if not changes:
                self.log_failure(f'command could not parse route in : {command}')
                reactor.processes.answer_error(service)
                yield True
                return

            for change in changes:
                change.nlri.action = Action.ANNOUNCE
                reactor.configuration.inject_change(peers, change)
                peer_list = ', '.join(peers) if peers else 'all peers'
                self.log_message(f'route added to {peer_list} : {change.extensive()}')
                yield False

            reactor.processes.answer_done(service)
        except ValueError:
            self.log_failure('issue parsing the route')
            reactor.processes.answer_error(service)
            yield True
        except IndexError:
            self.log_failure('issue parsing the route')
            reactor.processes.answer_error(service)
            yield True

    reactor.asynchronous.schedule(service, line, callback())
    return True


@Command.register('withdraw attribute')
@Command.register('withdraw attributes')
def withdraw_attribute(self, reactor, service, line, use_json):
    def callback():
        try:
            descriptions, command = extract_neighbors(line)
            peers = match_neighbors(reactor.peers(service), descriptions)
            if not peers:
                self.log_failure(f'no neighbor matching the command : {command}')
                reactor.processes.answer_error(service)
                yield True
                return

            changes = self.api_attributes(command, peers)
            if not changes:
                self.log_failure(f'command could not parse route in : {command}')
                reactor.processes.answer_error(service)
                yield True
                return

            for change in changes:
                change.nlri.action = Action.WITHDRAW
                if reactor.configuration.inject_change(peers, change):
                    peer_list = ', '.join(peers) if peers else 'all peers'
                    self.log_message(f'route removed from {peer_list} : {change.extensive()}')
                    yield False
                else:
                    peer_list = ', '.join(peers) if peers else 'all peers'
                    self.log_failure(f'route not found on {peer_list} : {change.extensive()}')
                    yield False

            reactor.processes.answer_done(service)
        except ValueError:
            self.log_failure('issue parsing the route')
            reactor.processes.answer_error(service)
            yield True
        except IndexError:
            self.log_failure('issue parsing the route')
            reactor.processes.answer_error(service)
            yield True

    reactor.asynchronous.schedule(service, line, callback())
    return True


@Command.register('announce flow')
def announce_flow(self, reactor, service, line, use_json):
    def callback():
        try:
            descriptions, command = extract_neighbors(line)
            peers = match_neighbors(reactor.peers(service), descriptions)
            if not peers:
                self.log_failure(f'no neighbor matching the command : {command}')
                reactor.processes.answer_error(service)
                yield True
                return

            changes = self.api_flow(command)
            if not changes:
                self.log_failure(f'command could not parse flow in : {command}')
                reactor.processes.answer_error(service)
                yield True
                return

            for change in changes:
                change.nlri.action = Action.ANNOUNCE
                reactor.configuration.inject_change(peers, change)
                peer_list = ', '.join(peers) if peers else 'all peers'
                self.log_message(f'flow added to {peer_list} : {change.extensive()}')
                yield False

            reactor.processes.answer_done(service)
        except ValueError:
            self.log_failure('issue parsing the flow')
            reactor.processes.answer_error(service)
            yield True
        except IndexError:
            self.log_failure('issue parsing the flow')
            reactor.processes.answer_error(service)
            yield True

    reactor.asynchronous.schedule(service, line, callback())
    return True


@Command.register('withdraw flow')
def withdraw_flow(self, reactor, service, line, use_json):
    def callback():
        try:
            descriptions, command = extract_neighbors(line)
            peers = match_neighbors(reactor.peers(service), descriptions)
            if not peers:
                self.log_failure(f'no neighbor matching the command : {command}')
                reactor.processes.answer_error(service)
                yield True
                return

            changes = self.api_flow(command)

            if not changes:
                self.log_failure(f'command could not parse flow in : {command}')
                reactor.processes.answer_error(service)
                yield True
                return

            for change in changes:
                change.nlri.action = Action.WITHDRAW
                if reactor.configuration.inject_change(peers, change):
                    peer_list = ', '.join(peers) if peers else 'all peers'
                    self.log_message(f'flow removed from {peer_list} : {change.extensive()}')
                else:
                    peer_list = ', '.join(peers) if peers else 'all peers'
                    self.log_failure(f'flow not found on {peer_list} : {change.extensive()}')
                yield False

            reactor.processes.answer_done(service)
        except ValueError:
            self.log_failure('issue parsing the flow')
            reactor.processes.answer_error(service)
            yield True
        except IndexError:
            self.log_failure('issue parsing the flow')
            reactor.processes.answer_error(service)
            yield True

    reactor.asynchronous.schedule(service, line, callback())
    return True


@Command.register('announce eor')
def announce_eor(self, reactor, service, line, use_json):
    def callback(self, command, peers):
        family = self.api_eor(command)
        if not family:
            self.log_failure(f'Command could not parse eor : {command}')
            reactor.processes.answer_error(service)
            yield True
            return

        reactor.configuration.inject_eor(peers, family)
        peer_list = ', '.join(peers if peers else []) if peers is not None else 'all peers'
        self.log_message(f'Sent to {peer_list} : {family.extensive()}')
        yield False

        reactor.processes.answer_done(service)

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


@Command.register('announce route-refresh')
def announce_refresh(self, reactor, service, line, use_json):
    def callback(self, command, peers):
        refreshes = self.api_refresh(command)
        if not refreshes:
            self.log_failure(f'Command could not parse route-refresh command : {command}')
            reactor.processes.answer_error(service)
            yield True
            return

        reactor.configuration.inject_refresh(peers, refreshes)
        for refresh in refreshes:
            peer_list = ', '.join(peers if peers else []) if peers is not None else 'all peers'
            self.log_message(f'Sent to {peer_list} : {refresh.extensive()}')

        yield False
        reactor.processes.answer_done(service)

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


@Command.register('announce operational')
def announce_operational(self, reactor, service, line, use_json):
    def callback(self, command, peers):
        operational = self.api_operational(command)
        if not operational:
            self.log_failure(f'Command could not parse operational command : {command}')
            reactor.processes.answer_error(service)
            yield True
            return

        reactor.configuration.inject_operational(peers, operational)
        peer_list = ', '.join(peers if peers else []) if peers is not None else 'all peers'
        self.log_message(f'operational message sent to {peer_list} : {operational.extensive()}')
        yield False
        reactor.processes.answer_done(service)

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


@Command.register('announce ipv4')
def announce_ipv4(self, reactor, service, line, use_json):
    def callback():
        try:
            descriptions, command = extract_neighbors(line)
            peers = match_neighbors(reactor.peers(service), descriptions)
            if not peers:
                self.log_failure(f'no neighbor matching the command : {command}')
                reactor.processes.answer_error(service)
                yield True
                return

            changes = self.api_announce_v4(command)
            if not changes:
                self.log_failure(f'command could not parse ipv4 in : {command}')
                reactor.processes.answer_error(service)
                yield True
                return

            for change in changes:
                change.nlri.action = Action.ANNOUNCE
                reactor.configuration.inject_change(peers, change)
                peer_list = ', '.join(peers) if peers else 'all peers'
                self.log_message(f'ipv4 added to {peer_list} : {change.extensive()}')
                yield False

            reactor.processes.answer_done(service)
        except ValueError:
            self.log_failure('issue parsing the ipv4')
            reactor.processes.answer_error(service)
            yield True
        except IndexError:
            self.log_failure('issue parsing the ipv4')
            reactor.processes.answer_error(service)
            yield True

    reactor.asynchronous.schedule(service, line, callback())
    return True


@Command.register('withdraw ipv4')
def withdraw_ipv4(self, reactor, service, line, use_json):
    def callback():
        try:
            descriptions, command = extract_neighbors(line)
            peers = match_neighbors(reactor.peers(service), descriptions)
            if not peers:
                self.log_failure(f'no neighbor matching the command : {command}')
                reactor.processes.answer_error(service)
                yield True
                return

            changes = self.api_announce_v4(command)

            if not changes:
                self.log_failure(f'command could not parse ipv4 in : {command}')
                reactor.processes.answer_error(service)
                yield True
                return

            for change in changes:
                change.nlri.action = Action.WITHDRAW
                if reactor.configuration.inject_change(peers, change):
                    peer_list = ', '.join(peers) if peers else 'all peers'
                    self.log_message(f'ipv4 removed from {peer_list} : {change.extensive()}')
                else:
                    peer_list = ', '.join(peers) if peers else 'all peers'
                    self.log_failure(f'ipv4 not found on {peer_list} : {change.extensive()}')
                yield False

            reactor.processes.answer_done(service)
        except ValueError:
            self.log_failure('issue parsing the ipv4')
            reactor.processes.answer_error(service)
            yield True
        except IndexError:
            self.log_failure('issue parsing the ipv4')
            reactor.processes.answer_error(service)
            yield True

    reactor.asynchronous.schedule(service, line, callback())
    return True


@Command.register('announce ipv6')
def announce_ipv6(self, reactor, service, line, use_json):
    def callback():
        try:
            descriptions, command = extract_neighbors(line)
            peers = match_neighbors(reactor.peers(service), descriptions)
            if not peers:
                self.log_failure(f'no neighbor matching the command : {command}')
                reactor.processes.answer_error(service)
                yield True
                return

            changes = self.api_announce_v6(command)
            if not changes:
                self.log_failure(f'command could not parse ipv6 in : {command}')
                reactor.processes.answer_error(service)
                yield True
                return

            for change in changes:
                change.nlri.action = Action.ANNOUNCE
                reactor.configuration.inject_change(peers, change)
                peer_list = ', '.join(peers) if peers else 'all peers'
                self.log_message(f'ipv6 added to {peer_list} : {change.extensive()}')
                yield False

            reactor.processes.answer_done(service)
        except ValueError:
            self.log_failure('issue parsing the ipv6')
            reactor.processes.answer_error(service)
            yield True
        except IndexError:
            self.log_failure('issue parsing the ipv6')
            reactor.processes.answer_error(service)
            yield True

    reactor.asynchronous.schedule(service, line, callback())
    return True


@Command.register('withdraw ipv6')
def withdraw_ipv6(self, reactor, service, line, use_json):
    def callback():
        try:
            descriptions, command = extract_neighbors(line)
            peers = match_neighbors(reactor.peers(service), descriptions)
            if not peers:
                self.log_failure(f'no neighbor matching the command : {command}')
                reactor.processes.answer_error(service)
                yield True
                return

            changes = self.api_announce_v6(command)

            if not changes:
                self.log_failure(f'command could not parse ipv6 in : {command}')
                reactor.processes.answer_error(service)
                yield True
                return

            for change in changes:
                change.nlri.action = Action.WITHDRAW
                if reactor.configuration.inject_change(peers, change):
                    peer_list = ', '.join(peers) if peers else 'all peers'
                    self.log_message(f'ipv6 removed from {peer_list} : {change.extensive()}')
                else:
                    peer_list = ', '.join(peers) if peers else 'all peers'
                    self.log_failure(f'ipv6 not found on {peer_list} : {change.extensive()}')
                yield False

            reactor.processes.answer_done(service)
        except ValueError:
            self.log_failure('issue parsing the ipv6')
            reactor.processes.answer_error(service)
            yield True
        except IndexError:
            self.log_failure('issue parsing the ipv6')
            reactor.processes.answer_error(service)
            yield True

    reactor.asynchronous.schedule(service, line, callback())
    return True
