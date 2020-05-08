# encoding: utf-8
"""
command/neighbor.py

Created by Thomas Mangin on 2017-07-01.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from datetime import timedelta

from exabgp.reactor.api.command.command import Command
from exabgp.reactor.api.command.limit import match_neighbor
from exabgp.reactor.api.command.limit import extract_neighbors


def register_neighbor():
    pass


def _en(value):
    if value is None:
        return 'n/a'
    return 'enabled' if value else 'disabled'


def _pr(value):
    if value is None:
        return 'n/a'
    return '%s' % value


class Neighbor(object):
    extensive_kv = '   %-20s %15s %15s %15s'
    extensive_template = """\
Neighbor %(peer-address)s

	Session                         Local
%(local-address)s
%(state)s
%(duration)s

	Setup                           Local          Remote
%(as)s
%(id)s
%(hold)s

	Capability                      Local          Remote
%(capabilities)s

	Families                        Local          Remote        Add-Path
%(families)s

	Message Statistic                Sent        Received
%(messages)s
""".replace(
        '\t', '  '
    )

    summary_header = 'Peer            AS        up/down state       |     #sent     #recvd'
    summary_template = '%-15s %-7s %9s %-12s %10d %10d'

    @classmethod
    def extensive(cls, answer):
        if answer['duration']:
            duration = cls.extensive_kv % ('up for', timedelta(seconds=answer['duration']), '', '')
        else:
            duration = cls.extensive_kv % ('down for', timedelta(seconds=answer['down']), '', '')
        formated = {
            'peer-address': answer['peer-address'],
            'local-address': cls.extensive_kv % ('local', answer['local-address'], '', ''),
            'state': cls.extensive_kv % ('state', answer['state'], '', ''),
            'duration': duration,
            'as': cls.extensive_kv % ('AS', answer['local-as'], _pr(answer['peer-as']), ''),
            'id': cls.extensive_kv % ('ID', answer['local-id'], _pr(answer['peer-id']), ''),
            'hold': cls.extensive_kv % ('hold-time', answer['local-hold'], _pr(answer['peer-hold']), ''),
            'capabilities': '\n'.join(
                cls.extensive_kv % ('%s:' % k, _en(l), _en(p), '') for k, (l, p) in answer['capabilities'].items()
            ),
            'families': '\n'.join(
                cls.extensive_kv % ('%s %s:' % (a, s), _en(l), _en(r), _en(p))
                for (a, s), (l, r, p) in answer['families'].items()
            ),
            'messages': '\n'.join(
                cls.extensive_kv % ('%s:' % k, str(s), str(r), '') for k, (s, r) in answer['messages'].items()
            ),
        }

        return cls.extensive_template % formated

    @classmethod
    def summary(cls, answer):
        return cls.summary_template % (
            answer['peer-address'],
            _pr(answer['peer-as']),
            timedelta(seconds=answer['duration']) if answer['duration'] else 'down',
            answer['state'].lower(),
            answer['messages']['update'][0],
            answer['messages']['update'][1],
        )


@Command.register('text', 'teardown', True)
def teardown(self, reactor, service, line):
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
                    self.log_message('teardown scheduled for %s' % ' '.join(description))
        reactor.processes.answer_done(service)
        return True
    except ValueError:
        reactor.processes.answer_error(service)
        return False
    except IndexError:
        reactor.processes.answer_error(service)
        return False


@Command.register('text', 'show neighbor', False, ['summary', 'extensive', 'configuration'])
def show_neighbor(self, reactor, service, command):
    words = command.split()

    extensive = 'extensive' in words
    configuration = 'configuration' in words
    summary = 'summary' in words

    if summary:
        words.remove('summary')
    if extensive:
        words.remove('extensive')
    if configuration:
        words.remove('configuration')

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

    def callback_extensive():
        for peer_name in reactor.peers():
            if limit and limit not in reactor.neighbor_name(peer_name):
                continue
            for line in Neighbor.extensive(reactor.neighbor_cli_data(peer_name)).split('\n'):
                reactor.processes.write(service, line)
                yield True
        reactor.processes.answer_done(service)

    def callback_summary():
        reactor.processes.write(service, Neighbor.summary_header)
        for peer_name in reactor.established_peers():
            if limit and limit != reactor.neighbor_ip(peer_name):
                continue
            for line in Neighbor.summary(reactor.neighbor_cli_data(peer_name)).split('\n'):
                reactor.processes.write(service, line)
                yield True
        reactor.processes.answer_done(service)

    if summary:
        reactor.asynchronous.schedule(service, command, callback_summary())
        return True

    if extensive:
        reactor.asynchronous.schedule(service, command, callback_extensive())
        return True

    if configuration:
        reactor.asynchronous.schedule(service, command, callback_configuration())
        return True

    reactor.processes.write(service, 'please specify summary, extensive or configuration')
    reactor.processes.write(service, 'you can filter by peer ip address adding it after the word neighbor')
    reactor.processes.answer_done(service)
