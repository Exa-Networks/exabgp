"""line/rib.py

Created by Thomas Mangin on 2017-07-01.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING, Any

from exabgp.bgp.message.update.nlri.evpn.nlri import EVPN
from exabgp.bgp.message.update.nlri.flow import Flow
from exabgp.bgp.message.update.nlri.inet import INET
from exabgp.bgp.message.update.nlri.nlri import NLRI
from exabgp.bgp.message.update.nlri.vpls import VPLS
from exabgp.bgp.neighbor import NeighborTemplate
from exabgp.environment import getenv

if TYPE_CHECKING:
    from exabgp.reactor.api import API
    from exabgp.reactor.loop import Reactor


def register_rib() -> None:
    pass


def _show_adjrib_callback(
    reactor: 'Reactor',
    service: str,
    last: str,
    route_type: tuple[type[NLRI], ...],
    advertised: bool,
    rib_name: str,
    extensive: bool,
    use_json: bool,
) -> Any:
    def to_text(key: str, changes: list[Any]) -> None:
        for change in changes:
            if not isinstance(change.nlri, route_type):
                # log something about this drop?
                continue

            neighbor = reactor.neighbor_name(key) if extensive else reactor.neighbor_ip(key)
            family = f'{change.nlri.family().afi_safi()[0]} {change.nlri.family().afi_safi()[1]}'
            details = change.extensive() if extensive else str(change.nlri)
            msg = f'{neighbor} {family} {details}'
            reactor.processes.write(service, msg)

    def to_json(key: str, changes: list[Any]) -> None:
        jason: dict[str, dict[str, Any]] = {}
        neighbor = reactor.neighbor(key)
        neighbor_ip = reactor.neighbor_ip(key)
        routes = jason.setdefault(neighbor_ip, {'routes': []})['routes']

        if extensive and neighbor is not None:
            jason[neighbor_ip].update(NeighborTemplate.formated_dict(reactor.neighbor_cli_data(key)))

        for change in changes:
            if not isinstance(change.nlri, route_type):
                # log something about this drop?
                continue

            # After isinstance check, change.nlri is one of the route_type(s)
            # which have a cidr attribute (INET, Flow, etc.)
            nlri: Any = change.nlri
            routes.append(
                {
                    'prefix': str(nlri.cidr.prefix()),
                    'family': str(change.nlri.family()).strip('()').replace(',', ''),
                },
            )

            for line in json.dumps(jason).split('\n'):
                reactor.processes.write(service, line)

    async def callback() -> None:
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
                await asyncio.sleep(0)  # Yield control after each chunk (matches original yield True)
        await reactor.processes.answer_done_async(service)

    return callback


def show_adj_rib(self: 'API', reactor: 'Reactor', service: str, peers: list[str], command: str, use_json: bool) -> bool:
    # command contains direction and options (e.g., "in extensive" or "out")
    words = command.split()
    extensive = 'extensive' in words

    # Get direction from first word
    rib = words[0] if words else ''
    if rib not in ('in', 'out'):
        reactor.processes.answer_error(service)
        return False

    klass: tuple[type[NLRI], ...] = (NLRI,)

    if 'inet' in words:
        klass = (INET,)
    elif 'flow' in words:
        klass = (Flow,)
    elif 'l2vpn' in words:
        klass = (VPLS, EVPN)

    if 'json' in words:
        words.remove('json')
        use_json = True

    for remove in ('in', 'out', 'extensive', 'inet', 'flow', 'l2vpn'):
        if remove in words:
            words.remove(remove)
    last = '' if not words else words[0]
    callback = _show_adjrib_callback(reactor, service, last, klass, False, rib, extensive, use_json)
    reactor.asynchronous.schedule(service, command, callback())
    return True


def flush_adj_rib_out(
    self: 'API', reactor: 'Reactor', service: str, peers: list[str], command: str, use_json: bool
) -> bool:
    async def callback(self: 'API', peer_list: list[str]) -> None:
        peer_names = ', '.join(peer_list) if peer_list else 'all peers'
        self.log_message(f'flushing adjb-rib out for {peer_names}')
        for peer_name in peer_list:
            reactor.neighbor_rib_resend(peer_name)
            await asyncio.sleep(0)  # Yield control after each peer (matches original yield False)

        await reactor.processes.answer_done_async(service)

    try:
        # peers list already parsed by dispatcher
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


def clear_adj_rib(
    self: 'API', reactor: 'Reactor', service: str, peers: list[str], command: str, use_json: bool
) -> bool:
    async def callback(self: 'API', peer_list: list[str], direction: str) -> None:
        peer_names = ', '.join(peer_list) if peer_list else 'all peers'
        self.log_message(f'clearing adjb-rib-{direction} for {peer_names}')
        for peer_name in peer_list:
            if direction == 'out':
                reactor.neighbor_rib_out_withdraw(peer_name)
            else:
                reactor.neighbor_rib_in_clear(peer_name)
            await asyncio.sleep(0)  # Yield control after each peer (matches original yield False)

        await reactor.processes.answer_done_async(service)

    try:
        # peers list already parsed by dispatcher
        if not peers:
            self.log_failure(f'no neighbor matching the command : {command}', 'warning')
            reactor.processes.answer_error(service)
            return False
        words = command.split()
        direction = 'in' if 'in' in words else 'out'
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
