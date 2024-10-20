# encoding: utf-8
"""
neighbor.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

import json

from copy import deepcopy

from collections import deque

from collections import Counter

from datetime import timedelta

from exabgp.protocol.family import AFI
# from exabgp.util.dns import host, domain

from exabgp.bgp.message import Message
from exabgp.bgp.message.open.capability import AddPath
from exabgp.bgp.message.open.holdtime import HoldTime

from exabgp.bgp.message.update.attribute import Attribute
from exabgp.bgp.message.update.attribute import NextHop

from exabgp.rib import RIB


# class Section(dict):
#     name = ''
#     key = ''
#     sub = ['capability']

#     def string(self, level=0):
#         prefix = ' ' * level
#         key_name = self.get(key,'')
#         returned = f'{prefix} {key_name} {\n'

#         prefix = ' ' * (level+1)
#         for k, v in self.items():
#             if k == prefix:
#                 continue
#             if k in sub:
#                 returned += self[k].string(level+1)
#             returned += f'{k} {v};\n'
#         return returned


# The definition of a neighbor (from reading the configuration)
class Neighbor(dict):
    class Capability(dict):
        defaults = {
            'asn4': True,
            'extended-message': True,
            'graceful-restart': False,
            'multi-session': False,
            'operational': False,
            'add-path': 0,
            'route-refresh': 0,
            'nexthop': None,
            'aigp': None,
            'software-version': None,
        }

    defaults = {
        # Those are the field from the configuration
        'description': '',
        'router-id': None,
        'local-address': None,
        'source-interface': None,
        'peer-address': None,
        'local-as': None,
        'peer-as': None,
        # passive indicate that we do not establish outgoing connections
        'passive': False,
        # the port to listen on ( zero mean that we do not listen )
        'listen': 0,
        # the port to connect to
        'connect': 0,
        'hold-time': HoldTime(180),
        'rate-limit': 0,
        'host-name': None,
        'domain-name': None,
        'group-updates': True,
        'auto-flush': True,
        'adj-rib-in': True,
        'adj-rib-out': True,
        'manual-eor': False,
        # XXX: this should be under an MD5 sub-dict/object ?
        'md5-password': None,
        'md5-base64': False,
        'md5-ip': None,
        'outgoing-ttl': None,
        'incoming-ttl': None,
    }

    _GLOBAL = {'uid': 1}

    def __init__(self):
        # super init
        self.update(self.defaults)

        # Those are subconf
        self.api = None  # XXX: not scriptable - is replaced outside the class

        # internal or calculated field
        self['capability'] = self.Capability.defaults.copy()

        # local_address uses auto discovery
        self.auto_discovery = False

        self.range_size = 1

        # was this Neighbor generated from a range
        self.generated = False

        self._families = []
        self._nexthop = []
        self._addpath = []
        self.rib = None

        # The routes we have parsed from the configuration
        self.changes = []
        self.previous = None

        self.eor = deque()
        self.asm = dict()

        self.messages = deque()
        self.refresh = deque()

        self.counter = Counter()
        # It is possible to :
        # - have multiple exabgp toward one peer on the same host ( use of pid )
        # - have more than once connection toward a peer
        # - each connection has it own neihgbor (hence why identificator is not in Protocol)
        self.uid = '%d' % self._GLOBAL['uid']
        self._GLOBAL['uid'] += 1

    def infer(self):
        if self['md5-ip'] is None:
            self['md5-ip'] = self['local-address']

        # Because (0 == False) == True when it should not!
        if self['capability']['graceful-restart'] is False:
            return
        if self['capability']['graceful-restart'] != 0:
            return

        self['capability']['graceful-restart'] = int(self['hold-time'])

    def id(self):
        return 'neighbor-%s' % self.uid

    # This set must be unique between peer, not full draft-ietf-idr-bgp-multisession-07
    def index(self):
        if self['listen'] != 0:
            return 'peer-ip %s listen %d' % (self['peer-address'], self['listen'])
        return self.name()

    def make_rib(self):
        self.rib = RIB(self.name(), self['adj-rib-in'], self['adj-rib-out'], self._families)

    # will resend all the routes once we reconnect
    def reset_rib(self):
        self.rib.reset()
        self.messages = deque()
        self.refresh = deque()

    # back to square one, all the routes are removed
    def clear_rib(self):
        self.rib.clear()
        self.messages = deque()
        self.refresh = deque()

    def name(self):
        if self['capability']['multi-session']:
            session = '/'.join('%s-%s' % (afi.name(), safi.name()) for (afi, safi) in self.families())
        else:
            session = 'in-open'
        return 'neighbor %s local-ip %s local-as %s peer-as %s router-id %s family-allowed %s' % (
            self['peer-address'],
            self['local-address'] if self['peer-address'] is not None else 'auto',
            self['local-as'] if self['local-as'] is not None else 'auto',
            self['peer-as'] if self['peer-as'] is not None else 'auto',
            self['router-id'],
            session,
        )

    def families(self):
        # this list() is important .. as we use the function to modify self._families
        return list(self._families)

    def nexthops(self):
        # this list() is important .. as we use the function to modify self._nexthop
        return list(self._nexthop)

    def addpaths(self):
        # this list() is important .. as we use the function to modify self._add_path
        return list(self._addpath)

    def add_family(self, family):
        # the families MUST be sorted for neighbor indexing name to be predictable for API users
        # this list() is important .. as we use the function to modify self._families
        if family not in self.families():
            afi, safi = family
            d = dict()
            d[afi] = [
                safi,
            ]
            for afi, safi in self._families:
                d.setdefault(afi, []).append(safi)
            self._families = [(afi, safi) for afi in sorted(d) for safi in sorted(d[afi])]

    def add_nexthop(self, afi, safi, nhafi):
        if (afi, safi, nhafi) not in self._nexthop:
            self._nexthop.append((afi, safi, nhafi))

    def add_addpath(self, family):
        # the families MUST be sorted for neighbor indexing name to be predictable for API users
        # this list() is important .. as we use the function to modify self._add_path
        if family not in self.addpaths():
            afi, safi = family
            d = dict()
            d[afi] = [
                safi,
            ]
            for afi, safi in self._addpath:
                d.setdefault(afi, []).append(safi)
            self._addpath = [(afi, safi) for afi in sorted(d) for safi in sorted(d[afi])]

    def remove_family(self, family):
        if family in self.families():
            self._families.remove(family)

    def remove_nexthop(self, afi, safi, nhafi):
        if (afi, safi, nhafi) in self.nexthops():
            self._nexthop.remove((afi, safi, nhafi))

    def remove_addpath(self, family):
        if family in self.addpaths():
            self._addpath.remove(family)

    def missing(self):
        if self['local-address'] is None and not self.auto_discovery:
            return 'local-address'
        if self['listen'] > 0 and self.auto_discovery:
            return 'local-address'
        if self['peer-address'] is None:
            return 'peer-address'
        if self.auto_discovery and not self['router-id']:
            return 'router-id'
        if self['peer-address'].afi == AFI.ipv6 and not self['router-id']:
            return 'router-id'
        return ''

    # This function only compares the neighbor BUT NOT ITS ROUTES
    def __eq__(self, other):
        # Comparing local_address is skipped in the case where either
        # peer is configured to auto discover its local address. In
        # this case it can happen that one local_address is None and
        # the other one will be set to the auto disocvered IP address.
        auto_discovery = self.auto_discovery or other.auto_discovery
        return (
            self['router-id'] == other['router-id']
            and self['local-as'] == other['local-as']
            and self['peer-address'] == other['peer-address']
            and self['peer-as'] == other['peer-as']
            and self['passive'] == other['passive']
            and self['listen'] == other['listen']
            and self['connect'] == other['connect']
            and self['hold-time'] == other['hold-time']
            and self['rate-limit'] == other['rate-limit']
            and self['host-name'] == other['host-name']
            and self['domain-name'] == other['domain-name']
            and self['md5-password'] == other['md5-password']
            and self['md5-ip'] == other['md5-ip']
            and self['incoming-ttl'] == other['incoming-ttl']
            and self['outgoing-ttl'] == other['outgoing-ttl']
            and self['group-updates'] == other['group-updates']
            and self['auto-flush'] == other['auto-flush']
            and self['adj-rib-in'] == other['adj-rib-in']
            and self['adj-rib-out'] == other['adj-rib-out']
            and (auto_discovery or self['local-address'] == other['local-address'])
            and self['capability'] == other['capability']
            and self.auto_discovery == other.auto_discovery
            and self.families() == other.families()
        )

    def __ne__(self, other):
        return not self.__eq__(other)

    def ip_self(self, afi):
        if afi == self['local-address'].afi:
            return self['local-address']

        # attempting to not barf for next-hop self when the peer is IPv6
        if afi == AFI.ipv4:
            return self['router-id']

        raise TypeError(
            'use of "next-hop self": the route (%s) does not have the same family as the BGP tcp session (%s)'
            % (afi, self['local-address'].afi)
        )

    def remove_self(self, changes):
        change = deepcopy(changes)
        if not change.nlri.nexthop.SELF:
            return change
        neighbor_self = self.ip_self(change.nlri.afi)
        change.nlri.nexthop = neighbor_self
        if Attribute.CODE.NEXT_HOP in change.attributes:
            change.attributes[Attribute.CODE.NEXT_HOP] = NextHop(str(neighbor_self), neighbor_self.pack())
        return change

    def __str__(self):
        return NeighborTemplate.configuration(self, False)


def _en(value):
    if value is None:
        return 'n/a'
    return 'enabled' if value else 'disabled'


def _pr(value):
    if value is None:
        return 'n/a'
    return '%s' % value


def _addpath(send, receive):
    if send and receive:
        return 'send/receive'
    if send:
        return 'send'
    if receive:
        return 'receive'
    return 'disabled'


class NeighborTemplate(object):
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
""".replace('\t', '  ')

    summary_header = 'Peer            AS        up/down state       |     #sent     #recvd'
    summary_template = '%-15s %-7s %9s %-12s %10d %10d'

    @classmethod
    def configuration(cls, neighbor, with_changes=True):
        changes = ''
        if with_changes:
            changes += '\nstatic { '
            for change in neighbor.rib.outgoing.queued_changes():
                changes += '\n\t\t%s' % change.extensive()
            changes += '\n}'

        families = ''
        for afi, safi in neighbor.families():
            families += '\n\t\t%s %s;' % (afi.name(), safi.name())

        nexthops = ''
        for afi, safi, nexthop in neighbor.nexthops():
            nexthops += '\n\t\t%s %s %s;' % (afi.name(), safi.name(), nexthop.name())

        addpaths = ''
        for afi, safi in neighbor.addpaths():
            addpaths += '\n\t\t%s %s;' % (afi.name(), safi.name())

        codes = Message.CODE

        _extension_global = {
            'neighbor-changes': 'neighbor-changes',
            'negotiated': 'negotiated',
            'fsm': 'fsm',
            'signal': 'signal',
        }

        _extension_receive = {
            'receive-packets': 'packets',
            'receive-parsed': 'parsed',
            'receive-consolidate': 'consolidate',
            'receive-%s' % codes.NOTIFICATION.SHORT: 'notification',
            'receive-%s' % codes.OPEN.SHORT: 'open',
            'receive-%s' % codes.KEEPALIVE.SHORT: 'keepalive',
            'receive-%s' % codes.UPDATE.SHORT: 'update',
            'receive-%s' % codes.ROUTE_REFRESH.SHORT: 'refresh',
            'receive-%s' % codes.OPERATIONAL.SHORT: 'operational',
        }

        _extension_send = {
            'send-packets': 'packets',
            'send-parsed': 'parsed',
            'send-consolidate': 'consolidate',
            'send-%s' % codes.NOTIFICATION.SHORT: 'notification',
            'send-%s' % codes.OPEN.SHORT: 'open',
            'send-%s' % codes.KEEPALIVE.SHORT: 'keepalive',
            'send-%s' % codes.UPDATE.SHORT: 'update',
            'send-%s' % codes.ROUTE_REFRESH.SHORT: 'refresh',
            'send-%s' % codes.OPERATIONAL.SHORT: 'operational',
        }

        apis = ''

        for process in neighbor.api.get('processes', []):
            _global = []
            _receive = []
            _send = []

            for api, name in _extension_global.items():
                _global.extend(
                    [
                        '\t\t%s;\n' % name,
                    ]
                    if process in neighbor.api[api]
                    else []
                )

            for api, name in _extension_receive.items():
                _receive.extend(
                    [
                        '\t\t\t%s;\n' % name,
                    ]
                    if process in neighbor.api[api]
                    else []
                )

            for api, name in _extension_send.items():
                _send.extend(
                    [
                        '\t\t\t%s;\n' % name,
                    ]
                    if process in neighbor.api[api]
                    else []
                )

            _api = '\tapi {\n'
            _api += '\t\tprocesses [ %s ];\n' % process
            _api += ''.join(_global)
            if _receive:
                _api += '\t\treceive {\n'
                _api += ''.join(_receive)
                _api += '\t\t}\n'
            if _send:
                _api += '\t\tsend {\n'
                _api += ''.join(_send)
                _api += '\t\t}\n'
            _api += '\t}\n'

            apis += _api

        returned = (
            'neighbor %s {\n'
            '\tdescription "%s";\n'
            '\trouter-id %s;\n'
            '\thost-name %s;\n'
            '\tdomain-name %s;\n'
            '\tlocal-address %s;\n'
            '\tsource-interface %s;\n'
            '\tlocal-as %s;\n'
            '\tpeer-as %s;\n'
            '\thold-time %s;\n'
            '\trate-limit %s;\n'
            '\tmanual-eor %s;\n'
            '%s%s%s%s%s%s%s%s%s%s%s\n'
            '\tcapability {\n'
            '%s%s%s%s%s%s%s%s%s%s\t}\n'
            '\tfamily {%s\n'
            '\t}\n'
            '\tnexthop {%s\n'
            '\t}\n'
            '\tadd-path {%s\n'
            '\t}\n'
            '%s'
            '%s'
            '}'
            % (
                neighbor['peer-address'],
                neighbor['description'],
                neighbor['router-id'],
                neighbor['host-name'],
                neighbor['domain-name'],
                neighbor['local-address'] if not neighbor.auto_discovery else 'auto',
                neighbor['source-interface'],
                neighbor['local-as'],
                neighbor['peer-as'],
                neighbor['hold-time'],
                'disable' if neighbor['rate-limit'] == 0 else neighbor['rate-limit'],
                'true' if neighbor['manual-eor'] else 'false',
                '\n\tpassive %s;\n' % ('true' if neighbor['passive'] else 'false'),
                '\n\tlisten %d;\n' % neighbor['listen'] if neighbor['listen'] else '',
                '\n\tconnect %d;\n' % neighbor['connect'] if neighbor['connect'] else '',
                '\tgroup-updates %s;\n' % ('true' if neighbor['group-updates'] else 'false'),
                '\tauto-flush %s;\n' % ('true' if neighbor['auto-flush'] else 'false'),
                '\tadj-rib-in %s;\n' % ('true' if neighbor['adj-rib-in'] else 'false'),
                '\tadj-rib-out %s;\n' % ('true' if neighbor['adj-rib-out'] else 'false'),
                '\tmd5-password "%s";\n' % neighbor['md5-password'] if neighbor['md5-password'] else '',
                '\tmd5-base64 %s;\n'
                % (
                    'true' if neighbor['md5-base64'] is True else 'false' if neighbor['md5-base64'] is False else 'auto'
                ),
                '\tmd5-ip "%s";\n' % neighbor['md5-ip'] if not neighbor.auto_discovery else '',
                '\toutgoing-ttl %s;\n' % neighbor['outgoing-ttl'] if neighbor['outgoing-ttl'] else '',
                '\tincoming-ttl %s;\n' % neighbor['incoming-ttl'] if neighbor['incoming-ttl'] else '',
                '\t\tasn4 %s;\n' % ('enable' if neighbor['capability']['asn4'] else 'disable'),
                '\t\troute-refresh %s;\n' % ('enable' if neighbor['capability']['route-refresh'] else 'disable'),
                '\t\tgraceful-restart %s;\n'
                % (
                    neighbor['capability']['graceful-restart']
                    if neighbor['capability']['graceful-restart']
                    else 'disable'
                ),
                '\t\tsoftware-version %s;\n' % ('enable' if neighbor['capability']['software-version'] else 'disable'),
                '\t\tnexthop %s;\n' % ('enable' if neighbor['capability']['nexthop'] else 'disable'),
                '\t\tadd-path %s;\n'
                % (
                    AddPath.string[neighbor['capability']['add-path']]
                    if neighbor['capability']['add-path']
                    else 'disable'
                ),
                '\t\tmulti-session %s;\n' % ('enable' if neighbor['capability']['multi-session'] else 'disable'),
                '\t\toperational %s;\n' % ('enable' if neighbor['capability']['operational'] else 'disable'),
                '\t\taigp %s;\n' % ('enable' if neighbor['capability']['aigp'] else 'disable'),
                families,
                nexthops,
                addpaths,
                apis,
                changes,
            )
        )

        # '\t\treceive {\n%s\t\t}\n' % receive if receive else '',
        # '\t\tsend {\n%s\t\t}\n' % send if send else '',
        return returned.replace('\t', '  ')

    @classmethod
    def as_dict(cls, answer):
        up = answer['duration']

        formated = {
            'state': 'up' if up else 'down',
            'duration': answer['duration'] if up else answer['down'],
            'fsm': answer['state'],
            'local': {
                'capabilities': {},
                'families': {},
                'add-path': {},
            },
            'peer': {
                'capabilities': {},
                'families': {},
                'add-path': {},
            },
            'messages': {'sent': {}, 'received': {}},
            'capabilities': [],
            'families': [],
            'add-path': {},
        }

        for (a, s), (lf, pf, aps, apr) in answer['families'].items():
            k = '%s %s' % (a, s)
            formated['local']['families'][k] = lf
            formated['peer']['families'][k] = pf
            formated['local']['add-path'][k] = aps
            formated['peer']['add-path'][k] = apr
            if lf and pf:
                formated['families'].append(k)
            formated['add-path'][k] = _addpath(aps, apr)

        for k, (lc, pc) in answer['capabilities'].items():
            formated['local']['capabilities'][k] = lc
            formated['peer']['capabilities'][k] = pc
            if locals and pc:
                formated['capabilities'].append(k)

        for k, (ms, mr) in answer['messages'].items():
            formated['messages']['sent'][k] = ms
            formated['messages']['received'][k] = mr

        formated['local']['address'] = answer['local-address']
        formated['local']['as'] = answer['local-as']
        formated['local']['id'] = answer['local-id']
        formated['local']['hold'] = answer['local-hold']

        formated['peer']['address'] = answer['peer-address']
        formated['peer']['as'] = answer['peer-as']
        formated['peer']['id'] = answer['peer-id']
        formated['peer']['hold'] = answer['peer-hold']

        return formated

    @classmethod
    def formated_dict(cls, answer):
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
                cls.extensive_kv % ('%s:' % k, _en(lc), _en(pc), '') for k, (lc, pc) in answer['capabilities'].items()
            ),
            'families': '\n'.join(
                cls.extensive_kv % ('%s %s:' % (a, s), _en(lf), _en(rf), _addpath(aps, apr))
                for (a, s), (lf, rf, apr, aps) in answer['families'].items()
            ),
            'messages': '\n'.join(
                cls.extensive_kv % ('%s:' % k, str(ms), str(mr), '') for k, (ms, mr) in answer['messages'].items()
            ),
        }

        return formated

    @classmethod
    def to_json(cls, answer):
        return json.dumps(cls.formated_dict(answer))

    @classmethod
    def extensive(cls, answer):
        return cls.extensive_template % cls.formated_dict(answer)

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
