"""line/rib.py

Created by Thomas Mangin on 2017-07-01.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import json

from exabgp.bgp.neighbor import NeighborTemplate

from exabgp.reactor.api.command.command import Command
from exabgp.reactor.api.command.limit import match_neighbors
from exabgp.reactor.api.command.limit import extract_neighbors

from exabgp.bgp.message.update.nlri.nlri import NLRI
from exabgp.bgp.message.update.nlri.inet import INET
from exabgp.bgp.message.update.nlri.flow import Flow
from exabgp.bgp.message.update.nlri.vpls import VPLS
from exabgp.bgp.message.update.nlri.evpn.nlri import EVPN

from exabgp.environment import getenv


def register_rib():
    pass


def _show_adjrib_callback(reactor, service, last, route_type, advertised, rib_name, extensive, use_json):
    def to_text(key, changes):
        for change in changes:
            if not isinstance(change.nlri, route_type):
                # log something about this drop?
                continue

            neighbor = reactor.neighbor_name(key) if extensive else reactor.neighbor_ip(key)
            family = f'{change.nlri.family().afi_safi()[0]} {change.nlri.family().afi_safi()[1]}'
            details = change.extensive() if extensive else str(change.nlri)
            msg = f'{neighbor} {family} {details}'
            reactor.processes.write(service, msg)

    def to_json(key, changes):
        jason = {}
        neighbor = reactor.neighbor(key)
        neighbor_ip = reactor.neighbor_ip(key)
        routes = jason.setdefault(neighbor_ip, {'routes': []})['routes']

        if extensive:
            jason[neighbor_ip].update(NeighborTemplate.to_json(neighbor))

        for change in changes:
            if not isinstance(change.nlri, route_type):
                # log something about this drop?
                continue

            routes.append(
                {
                    'prefix': str(change.nlri.cidr.prefix()),
                    'family': str(change.nlri.family()).strip('()').replace(',', ''),
                },
            )

            for line in json.dumps(jason).split('\n'):
                reactor.processes.write(service, line)

    def callback():
        lines_per_yield = getenv().api.chunk
        if last in ('routes', 'extensive', 'static', 'flow', 'l2vpn'):
            peers = reactor.peers()
        else:
            peers = [n for n in reactor.peers() if f'neighbor {last}' in n]
        for key in peers:
            routes = reactor.neighor_rib(key, rib_name, advertised)
            while routes:
                changes, routes = routes[:lines_per_yield], routes[lines_per_yield:]
                if use_json:
                    to_json(key, changes)
                else:
                    to_text(key, changes)
                yield True
        reactor.processes.answer_done(service)

    return callback


@Command.register(
    'show adj-rib out',
    False,
    [
        'extensive',
    ],
    True,
)
@Command.register(
    'show adj-rib in',
    False,
    [
        'extensive',
    ],
    True,
)
def show_adj_rib(self, reactor, service, line, use_json):
    words = line.split()
    extensive = line.endswith(' extensive')
    try:
        rib = words[2]
        if rib not in ('in', 'out'):
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

    if 'json' in words:
        words.remove('json')
        use_json = True

    for remove in ('show', 'adj-rib', 'adj-rib-in', 'adj-rib-out', 'in', 'out', 'extensive'):
        if remove in words:
            words.remove(remove)
    last = '' if not words else words[0]
    callback = _show_adjrib_callback(reactor, service, last, klass, False, rib, extensive, use_json)
    reactor.asynchronous.schedule(service, line, callback())
    return True


@Command.register('flush adj-rib out')
def flush_adj_rib_out(self, reactor, service, line, use_json):
    def callback(self, peers):
        peer_list = ', '.join(peers if peers else []) if peers is not None else 'all peers'
        self.log_message(f'flushing adjb-rib out for {peer_list}')
        for peer_name in peers:
            reactor.neighbor_rib_resend(peer_name)
            yield False

        reactor.processes.answer_done(service)

    try:
        descriptions, command = extract_neighbors(line)
        peers = match_neighbors(reactor.established_peers(), descriptions)
        if not peers:
            self.log_failure(f'no neighbor matching the command : {command}', 'warning')
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


@Command.register('clear adj-rib')
def clear_adj_rib(self, reactor, service, line, use_json):
    def callback(self, peers, direction):
        peer_list = ', '.join(peers if peers else []) if peers is not None else 'all peers'
        self.log_message(f'clearing adjb-rib-{direction} for {peer_list}')
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
            self.log_failure(f'no neighbor matching the command : {command}', 'warning')
            reactor.processes.answer_error(service)
            return False
        words = command.split()
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
