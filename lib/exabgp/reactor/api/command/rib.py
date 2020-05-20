# encoding: utf-8
"""
line/rib.py

Created by Thomas Mangin on 2017-07-01.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from exabgp.reactor.api.command.command import Command
from exabgp.reactor.api.command.limit import match_neighbors
from exabgp.reactor.api.command.limit import extract_neighbors

from exabgp.bgp.message.update.nlri.nlri import NLRI
from exabgp.bgp.message.update.nlri.inet import INET
from exabgp.bgp.message.update.nlri.flow import Flow
from exabgp.bgp.message.update.nlri.vpls import VPLS
from exabgp.bgp.message.update.nlri.evpn.nlri import EVPN

from exabgp.configuration.environment import environment


def register_rib():
    pass


def _show_adjrib_callback(reactor, service, last, route_type, advertised, rib_name, extensive):
    def callback():
        lines_per_yield = environment.settings().api.chunk
        if last in ('routes', 'extensive', 'static', 'flow', 'l2vpn'):
            peers = reactor.peers()
        else:
            peers = [n for n in reactor.peers() if 'neighbor %s' % last in n]
        for key in peers:
            routes = reactor.neighor_rib(key, rib_name, advertised)
            while routes:
                changes, routes = routes[:lines_per_yield], routes[lines_per_yield:]
                for change in changes:
                    if isinstance(change.nlri, route_type):
                        if extensive:
                            reactor.processes.write(
                                service,
                                '%s %s %s'
                                % (reactor.neighbor_name(key), '%s %s' % change.nlri.family(), change.extensive()),
                            )
                        else:
                            reactor.processes.write(
                                service,
                                'neighbor %s %s %s'
                                % (reactor.neighbor_ip(key), '%s %s' % change.nlri.family(), str(change.nlri)),
                            )
                yield True
        reactor.processes.answer_done(service)

    return callback


@Command.register('text', 'show adj-rib out', False, ['extensive',])
@Command.register('text', 'show adj-rib in', False, ['extensive',])
def show_adj_rib(self, reactor, service, line):
    words = line.split()
    extensive = line.endswith(' extensive')
    try:
        rib = words[2]
        if not rib in ('in', 'out'):
            reactor.processes.answer_error(service)
            return False
    except IndexError:
        if words[1] == 'adj-rib-in':
            rib = 'in'
        elif words[1] == 'adj-rib-out':
            rib = 'out'
        else:
            reactor.processes.answer_error(service)
            return False

    if rib not in ('in', 'out'):
        reactor.processes.answer_error(service)
        return False

    klass = NLRI

    if 'inet' in words:
        klass = INET
    elif 'flow' in words:
        klass = Flow
    elif 'l2vpn' in words:
        klass = (VPLS, EVPN)

    for remove in ('show', 'adj-rib', 'adj-rib-in', 'adj-rib-out', 'in', 'out', 'extensive'):
        if remove in words:
            words.remove(remove)
    last = '' if not words else words[0]
    callback = _show_adjrib_callback(reactor, service, last, klass, False, rib, extensive)
    reactor.asynchronous.schedule(service, line, callback())
    return True


@Command.register('text', 'flush adj-rib out')
def flush_adj_rib_out(self, reactor, service, line):
    def callback(self, peers):
        self.log_message(
            "Flushing adjb-rib out for %s" % ', '.join(peers if peers else []) if peers is not None else 'all peers'
        )
        for peer_name in peers:
            reactor.neighbor_rib_resend(peer_name)
            yield False

        reactor.processes.answer_done(service)

    try:
        descriptions, command = extract_neighbors(line)
        peers = match_neighbors(reactor.established_peers(), descriptions)
        if not peers:
            self.log_failure('no neighbor matching the command : %s' % command, 'warning')
            reactor.processes.answer_error(service)
            return False
        reactor.asynchronous.schedule(service, command, callback(self, peers))
        return True
    except ValueError:
        self.log_failure('issue parsing the command')
        reactor.processes.answer_error(service)
        return False
    except IndexError:
        self.log_failure('issue parsing the command')
        reactor.processes.answer_error(service)
        return False


@Command.register('text', 'clear adj-rib')
def clear_adj_rib(self, reactor, service, line):
    def callback(self, peers, direction):
        self.log_message(
            "clearing adjb-rib-%s for %s"
            % (direction, ', '.join(peers if peers else []) if peers is not None else 'all peers')
        )
        for peer_name in peers:
            if direction == 'out':
                reactor.neighbor_rib_out_withdraw(peer_name)
            else:
                reactor.neighbor_rib_in_clear(peer_name)
            yield False

        reactor.processes.answer_done(service)

    try:
        descriptions, command = extract_neighbors(line)
        peers = match_neighbors(reactor.peers(), descriptions)
        if not peers:
            self.log_failure('no neighbor matching the command : %s' % command, 'warning')
            reactor.processes.answer_error(service)
            return False
        words = line.split()
        direction = 'in' if 'adj-rib-in' in words or 'in' in words else 'out'
        reactor.asynchronous.schedule(service, command, callback(self, peers, direction))
        return True
    except ValueError:
        self.log_failure('issue parsing the command')
        reactor.processes.answer_error(service)
        return False
    except IndexError:
        self.log_failure('issue parsing the command')
        reactor.processes.answer_error(service)
        return False
