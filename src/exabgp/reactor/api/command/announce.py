# encoding: utf-8
"""
line/watchdog.py

Created by Thomas Mangin on 2017-07-01.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from exabgp.reactor.api.command.command import Command
from exabgp.reactor.api.command.limit import match_neighbors
from exabgp.reactor.api.command.limit import extract_neighbors

from exabgp.protocol.ip import NoNextHop
from exabgp.bgp.message import OUT
from exabgp.bgp.message.update.attribute import NextHop

from exabgp.configuration.static import ParseStaticRoute


def register_announce():
    pass


@Command.register('text', 'announce route')
def announce_route(self, reactor, service, line):
    def callback():
        try:
            descriptions, command = extract_neighbors(line)
            peers = match_neighbors(reactor.peers(), descriptions)
            if not peers:
                self.log_failure('no neighbor matching the command : %s' % command)
                reactor.processes.answer_error(service)
                yield True
                return

            changes = self.api_route(command)
            if not changes:
                self.log_failure('command could not parse route in : %s' % command)
                reactor.processes.answer_error(service)
                yield True
                return

            for change in changes:
                if not ParseStaticRoute.check(change):
                    self.log_message(
                        'invalid route for %s : %s' % (', '.join(peers) if peers else 'all peers', change.extensive())
                    )
                    continue
                change.nlri.action = OUT.ANNOUNCE
                reactor.configuration.inject_change(peers, change)
                self.log_message(
                    'route added to %s : %s' % (', '.join(peers) if peers else 'all peers', change.extensive())
                )
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


@Command.register('text', 'withdraw route')
def withdraw_route(self, reactor, service, line):
    def callback():
        try:
            descriptions, command = extract_neighbors(line)
            peers = match_neighbors(reactor.peers(), descriptions)
            if not peers:
                self.log_failure('no neighbor matching the command : %s' % command)
                reactor.processes.answer_error(service)
                yield True
                return

            changes = self.api_route(command)
            if not changes:
                self.log_failure('command could not parse route in : %s' % command)
                reactor.processes.answer_error(service)
                yield True
                return

            for change in changes:
                # Change the action to withdraw before checking the route
                change.nlri.action = OUT.WITHDRAW
                # NextHop is a mandatory field (but we do not require in)
                if change.nlri.nexthop is NoNextHop:
                    change.nlri.nexthop = NextHop('0.0.0.0')

                if not ParseStaticRoute.check(change):
                    self.log_message(
                        'invalid route for %s : %s' % (', '.join(peers) if peers else 'all peers', change.extensive())
                    )
                    continue
                if reactor.configuration.inject_change(peers, change):
                    self.log_message(
                        'route removed from %s : %s' % (', '.join(peers) if peers else 'all peers', change.extensive())
                    )
                    yield False
                else:
                    self.log_failure(
                        'route not found on %s : %s' % (', '.join(peers) if peers else 'all peers', change.extensive())
                    )
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


@Command.register('text', 'announce vpls')
def announce_vpls(self, reactor, service, line):
    def callback():
        try:
            descriptions, command = extract_neighbors(line)
            peers = match_neighbors(reactor.peers(), descriptions)
            if not peers:
                self.log_failure('no neighbor matching the command : %s' % command)
                reactor.processes.answer_error(service)
                yield True
                return

            changes = self.api_vpls(command)
            if not changes:
                self.log_failure('command could not parse vpls in : %s' % command)
                reactor.processes.answer_error(service)
                yield True
                return

            for change in changes:
                change.nlri.action = OUT.ANNOUNCE
                reactor.configuration.inject_change(peers, change)
                self.log_message(
                    'vpls added to %s : %s' % (', '.join(peers) if peers else 'all peers', change.extensive())
                )
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


@Command.register('text', 'withdraw vpls')
def withdraw_vpls(self, reactor, service, line):
    def callback():
        try:
            descriptions, command = extract_neighbors(line)
            peers = match_neighbors(reactor.peers(), descriptions)
            if not peers:
                self.log_failure('no neighbor matching the command : %s' % command)
                reactor.processes.answer_error(service)
                yield True
                return

            changes = self.api_vpls(command)

            if not changes:
                self.log_failure('command could not parse vpls in : %s' % command)
                reactor.processes.answer_error(service)
                yield True
                return

            for change in changes:
                change.nlri.action = OUT.WITHDRAW
                if reactor.configuration.inject_change(peers, change):
                    self.log_message(
                        'vpls removed from %s : %s' % (', '.join(peers) if peers else 'all peers', change.extensive())
                    )
                    yield False
                else:
                    self.log_failure(
                        'vpls not found on %s : %s' % (', '.join(peers) if peers else 'all peers', change.extensive())
                    )
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


@Command.register('text', 'announce attribute')
@Command.register('text', 'announce attributes')
def announce_attributes(self, reactor, service, line):
    def callback():
        try:
            descriptions, command = extract_neighbors(line)
            peers = match_neighbors(reactor.peers(), descriptions)
            if not peers:
                self.log_failure('no neighbor matching the command : %s' % command)
                reactor.processes.answer_error(service)
                yield True
                return

            changes = self.api_attributes(command, peers)
            if not changes:
                self.log_failure('command could not parse route in : %s' % command)
                reactor.processes.answer_error(service)
                yield True
                return

            for change in changes:
                change.nlri.action = OUT.ANNOUNCE
                reactor.configuration.inject_change(peers, change)
                self.log_message(
                    'route added to %s : %s' % (', '.join(peers) if peers else 'all peers', change.extensive())
                )
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


@Command.register('text', 'withdraw attributes')
def withdraw_attribute(self, reactor, service, line):
    def callback():
        try:
            descriptions, command = extract_neighbors(line)
            peers = match_neighbors(reactor.peers(), descriptions)
            if not peers:
                self.log_failure('no neighbor matching the command : %s' % command)
                reactor.processes.answer_error(service)
                yield True
                return

            changes = self.api_attributes(command, peers)
            if not changes:
                self.log_failure('command could not parse route in : %s' % command)
                reactor.processes.answer_error(service)
                yield True
                return

            for change in changes:
                change.nlri.action = OUT.WITHDRAW
                if reactor.configuration.inject_change(peers, change):
                    self.log_message(
                        'route removed from %s : %s' % (', '.join(peers) if peers else 'all peers', change.extensive())
                    )
                    yield False
                else:
                    self.log_failure(
                        'route not found on %s : %s' % (', '.join(peers) if peers else 'all peers', change.extensive())
                    )
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


@Command.register('text', 'announce flow')
def announce_flow(self, reactor, service, line):
    def callback():
        try:
            descriptions, command = extract_neighbors(line)
            peers = match_neighbors(reactor.peers(), descriptions)
            if not peers:
                self.log_failure('no neighbor matching the command : %s' % command)
                reactor.processes.answer_error(service)
                yield True
                return

            changes = self.api_flow(command)
            if not changes:
                self.log_failure('command could not parse flow in : %s' % command)
                reactor.processes.answer_error(service)
                yield True
                return

            for change in changes:
                change.nlri.action = OUT.ANNOUNCE
                reactor.configuration.inject_change(peers, change)
                self.log_message(
                    'flow added to %s : %s' % (', '.join(peers) if peers else 'all peers', change.extensive())
                )
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


@Command.register('text', 'withdraw flow')
def withdraw_flow(self, reactor, service, line):
    def callback():
        try:
            descriptions, command = extract_neighbors(line)
            peers = match_neighbors(reactor.peers(), descriptions)
            if not peers:
                self.log_failure('no neighbor matching the command : %s' % command)
                reactor.processes.answer_error(service)
                yield True
                return

            changes = self.api_flow(command)

            if not changes:
                self.log_failure('command could not parse flow in : %s' % command)
                reactor.processes.answer_error(service)
                yield True
                return

            for change in changes:
                change.nlri.action = OUT.WITHDRAW
                if reactor.configuration.inject_change(peers, change):
                    self.log_message(
                        'flow removed from %s : %s' % (', '.join(peers) if peers else 'all peers', change.extensive())
                    )
                else:
                    self.log_failure(
                        'flow not found on %s : %s' % (', '.join(peers) if peers else 'all peers', change.extensive())
                    )
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


@Command.register('text', 'announce eor')
def announce_eor(self, reactor, service, command):
    def callback(self, command, peers):
        family = self.api_eor(command)
        if not family:
            self.log_failure("Command could not parse eor : %s" % command)
            reactor.processes.answer_error(service)
            yield True
            return

        reactor.configuration.inject_eor(peers, family)
        self.log_message(
            "Sent to %s : %s"
            % (', '.join(peers if peers else []) if peers is not None else 'all peers', family.extensive())
        )
        yield False

        reactor.processes.answer_done(service)

    try:
        descriptions, command = extract_neighbors(command)
        peers = match_neighbors(reactor.established_peers(), descriptions)
        if not peers:
            self.log_failure('no neighbor matching the command : %s' % command)
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


@Command.register('text', 'announce route-refresh')
def announce_refresh(self, reactor, service, command):
    def callback(self, command, peers):
        refreshes = self.api_refresh(command)
        if not refreshes:
            self.log_failure("Command could not parse route-refresh command : %s" % command)
            reactor.processes.answer_error(service)
            yield True
            return

        reactor.configuration.inject_refresh(peers, refreshes)
        for refresh in refreshes:
            self.log_message(
                "Sent to %s : %s"
                % (', '.join(peers if peers else []) if peers is not None else 'all peers', refresh.extensive())
            )

        yield False
        reactor.processes.answer_done(service)

    try:
        descriptions, command = extract_neighbors(command)
        peers = match_neighbors(reactor.established_peers(), descriptions)
        if not peers:
            self.log_failure('no neighbor matching the command : %s' % command)
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


@Command.register('text', 'announce operational')
def announce_operational(self, reactor, service, command):
    def callback(self, command, peers):
        operational = self.api_operational(command)
        if not operational:
            self.log_failure("Command could not parse operational command : %s" % command)
            reactor.processes.answer_error(service)
            yield True
            return

        reactor.configuration.inject_operational(peers, operational)
        self.log_message(
            "operational message sent to %s : %s"
            % (', '.join(peers if peers else []) if peers is not None else 'all peers', operational.extensive())
        )
        yield False
        reactor.processes.answer_done(service)

    if (command.split() + ['be', 'safe'])[2].lower() not in (
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
        descriptions, command = extract_neighbors(command)
        peers = match_neighbors(reactor.peers(), descriptions)
        if not peers:
            self.log_failure('no neighbor matching the command : %s' % command)
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
