"""command/neighbor.py

Created by Thomas Mangin on 2017-07-01.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import json

from exabgp.bgp.neighbor import NeighborTemplate

from exabgp.reactor.api.command.limit import match_neighbor
from exabgp.reactor.api.command.limit import extract_neighbors

from exabgp.reactor.api.command.command import Command


def register_neighbor():
    pass


@Command.register('teardown', True)
def teardown(self, reactor, service, line, use_json):
    try:
        descriptions, line = extract_neighbors(line)
        if ' ' not in line:
            reactor.processes.answer_error(service)
            return False
        _, code = line.split(' ', 1)
        if not code.isdigit():
            reactor.processes.answer_error(service)
            return False
        for key in reactor.established_peers():
            for description in descriptions:
                if match_neighbor(description, key):
                    reactor.teardown_peer(key, int(code))
                    desc_str = ' '.join(description)
                    self.log_message(f'teardown scheduled for {desc_str}')
        reactor.processes.answer_done(service)
        return True
    except ValueError:
        reactor.processes.answer_error(service)
        return False
    except IndexError:
        reactor.processes.answer_error(service)
        return False


@Command.register('show neighbor', False, ['summary', 'extensive', 'configuration'], True)
def show_neighbor(self, reactor, service, line, use_json):
    words = line.split()

    extensive = 'extensive' in words
    configuration = 'configuration' in words
    summary = 'summary' in words
    jason = 'json' in words
    text = 'text' in words

    if summary:
        words.remove('summary')
    if extensive:
        words.remove('extensive')
    if configuration:
        words.remove('configuration')
    if jason:
        words.remove('json')
    if text:
        words.remove('text')

    limit = words[-1] if words[-1] != 'neighbor' else ''

    def callback_configuration():
        for neighbor_name in reactor.configuration.neighbors.keys():
            neighbor = reactor.configuration.neighbors.get(neighbor_name, None)
            if not neighbor:
                continue
            if limit and limit not in neighbor_name:
                continue
            for line in str(neighbor).split('\n'):
                reactor.processes.write(service, line)
                yield True
        reactor.processes.answer_done(service)

    def callback_json():
        p = []
        for peer_name in reactor.peers():
            p.append(NeighborTemplate.as_dict(reactor.neighbor_cli_data(peer_name)))
        for line in json.dumps(p).split('\n'):
            reactor.processes.write(service, line)
            yield True
        reactor.processes.answer_done(service)

    def callback_extensive():
        for peer_name in reactor.peers():
            if limit and limit not in reactor.neighbor_name(peer_name):
                continue
            for line in NeighborTemplate.extensive(reactor.neighbor_cli_data(peer_name)).split('\n'):
                reactor.processes.write(service, line)
                yield True
        reactor.processes.answer_done(service)

    def callback_summary():
        reactor.processes.write(service, NeighborTemplate.summary_header)
        for peer_name in reactor.peers():
            if limit and limit != reactor.neighbor_ip(peer_name):
                continue
            for line in NeighborTemplate.summary(reactor.neighbor_cli_data(peer_name)).split('\n'):
                reactor.processes.write(service, line)
                yield True
        reactor.processes.answer_done(service)

    if use_json:
        reactor.asynchronous.schedule(service, line, callback_json())
        return True

    if summary:
        reactor.asynchronous.schedule(service, line, callback_summary())
        return True

    if extensive:
        reactor.asynchronous.schedule(service, line, callback_extensive())
        return True

    if configuration:
        reactor.asynchronous.schedule(service, line, callback_configuration())
        return True

    reactor.processes.write(service, 'please specify summary, extensive or configuration')
    reactor.processes.write(service, 'you can filter by peer ip address adding it after the word neighbor')
    reactor.processes.answer_done(service)
