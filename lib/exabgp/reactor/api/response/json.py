#!/usr/bin/env python
# encoding: utf-8
"""
Response/json.py

Created by Thomas Mangin on 2012-12-30.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

import os
import socket
import sys
import time
import signal

from exabgp.vendoring import six

from exabgp.util import hexstring

from exabgp.bgp.message import Message
from exabgp.bgp.message import IN

from exabgp.configuration.environment import environment
from exabgp.bgp.message.open.capability.refresh import REFRESH


if sys.version_info > (3,):
    long = int

SIGNAL_NAME = dict(
    (k, v) for v, k in reversed(sorted(signal.__dict__.items())) if v.startswith('SIG') and not v.startswith('SIG_')
)


def nop(_):
    return _


class JSON(object):
    _count = {}

    def __init__(self, version):
        self.version = version
        self.time = nop
        self.compact = environment.settings().api.compact

    # def _reset (self, neighbor):
    # 	self._count[neighbor.uid] = 0
    # 	return 0

    def _counter(self, neighbor):
        increased = self._count.get(neighbor.uid, 0) + 1
        self._count[neighbor.uid] = increased
        return increased

    def _string(self, object):
        if issubclass(object.__class__, bool):
            return 'true' if object else 'false'
        if issubclass(object.__class__, long):
            return '%s' % object
        if issubclass(object.__class__, int):
            return '%s' % object
        string = '%s' % object
        if '{' in string:
            return string
        if '[' in string:
            return string
        return '"%s"' % object

    def _header(self, content, header, body, neighbor, message_type=None):
        peer = '"host" : "%s", ' % socket.gethostname()
        pid = '"pid" : %s, ' % os.getpid()
        ppid = '"ppid" : %s, ' % os.getppid()
        counter = '"counter": %s, ' % self._counter(neighbor) if neighbor is not None else ''
        header = '"header": "%s", ' % hexstring(header) if header else ''
        body = '"body": "%s", ' % hexstring(body) if body else ''
        mtype = '"type": "%s", ' % message_type if message_type else 'default'

        return (
            '{ '
            '"exabgp": "%s", '
            '"time": %s, '
            '%s%s%s%s%s%s%s%s '
            '}' % (self.version, self.time(time.time()), peer, pid, ppid, counter, mtype, header, body, content)
        )

    __neighbor = '''\
"neighbor": {
	"address": { "local": "%s", "peer": "%s" },
	"asn": { "local": %s, "peer": %s }
	%s%s%s%s
}'''.replace(
        '\t', ''
    ).replace(
        '\n', ' '
    )

    def _neighbor(self, neighbor, direction, content):
        return self.__neighbor % (
            neighbor.local_address,
            neighbor.peer_address,
            neighbor.local_as,
            neighbor.peer_as,
            ', ' if direction else '',
            '"direction": "%s"' % direction if direction else '',
            ', ' if content else ' ',
            content,
        )

    def _kv(self, extra):
        return ", ".join('"%s": %s' % (k, self._string(v)) for (k, v) in six.iteritems(extra))

    def _json_kv(self, extra):
        return ", ".join('"%s": %s' % (k, v.json()) for (k, v) in six.iteritems(extra))

    def _json_list(self, extra):
        return ", ".join('%s' % (v.json()) for v in six.iteritems(extra))

    def _minimalkv(self, extra):
        return ", ".join('"%s": %s' % (k, self._string(v)) for (k, v) in six.iteritems(extra) if v)

    def up(self, neighbor):
        return self._header(
            self._neighbor(neighbor, None, self._kv({'state': 'up',})), '', '', neighbor, message_type='state'
        )

    def connected(self, neighbor):
        return self._header(
            self._neighbor(neighbor, None, self._kv({'state': 'connected',})), '', '', neighbor, message_type='state'
        )

    def down(self, neighbor, reason=''):
        def escape_quote(reason):
            # the {} and [] change is an horrible hack until we generate python objects
            # as otherwise we interpret the string as a list or dict
            return reason.replace('[', '(').replace(']', ')').replace('{', '(').replace('}', ')').replace('"', '\\"')

        return self._header(
            self._neighbor(neighbor, None, self._kv({'state': 'down', 'reason': escape_quote(reason),})),
            '',
            '',
            neighbor,
            message_type='state',
        )

    def shutdown(self):
        return self._header(self._kv({'notification': 'shutdown',}), '', '', None, message_type='notification')

    def _negotiated(self, negotiated):
        return {
            'negotiated': '{ %s } '
            % self._kv(
                {
                    'message_size': negotiated.msg_size,
                    'hold_time': negotiated.holdtime,
                    'asn4': negotiated.asn4,
                    'multisession': negotiated.multisession,
                    'operational': negotiated.operational,
                    'refresh': REFRESH.json(negotiated.refresh),
                    'families': '[ %s ]' % ' ,'.join(['"%s %s"' % family for family in negotiated.families]),
                    'nexthop': '[ %s ]' % ' ,'.join(['"%s %s %s"' % family for family in negotiated.nexthop]),
                    'add_path': '{ "send": %s, "receive": %s }'
                    % (
                        '[ %s ]'
                        % ', '.join([family for family in negotiated.families if negotiated.addpath.send(*family)]),
                        '[ %s ]'
                        % ', '.join(
                            [
                                '"%s %s"' % family
                                for family in negotiated.families
                                if negotiated.addpath.receive(*family)
                            ]
                        ),
                    ),
                }
            )
        }

    def negotiated(self, neighbor, negotiated):
        return self._header(
            self._neighbor(neighbor, None, self._kv(self._negotiated(negotiated))),
            '',
            '',
            neighbor,
            message_type='negotiated',
        )

    def fsm(self, neighbor, fsm):
        return self._header(
            self._neighbor(neighbor, None, self._kv({'state': fsm.name()})), '', '', neighbor, message_type='fsm'
        )

    def signal(self, neighbor, signal):
        return self._header(
            self._neighbor(
                neighbor, None, self._kv({'code': '%d' % signal, 'name': SIGNAL_NAME.get(signal, 'UNKNOWN'),})
            ),
            '',
            '',
            neighbor,
            message_type='signal',
        )

    def notification(self, neighbor, direction, message, negotiated, header, body):
        return self._header(
            self._neighbor(
                neighbor,
                direction,
                self._kv(
                    {
                        'notification': '{ %s } '
                        % self._kv({'code': message.code, 'subcode': message.subcode, 'data': hexstring(message.data),})
                    }
                ),
            ),
            header,
            body,
            neighbor,
            message_type='notification',
        )

    def packets(self, neighbor, direction, category, negotiated, header, body):
        message = {
            'message': '{ %s } '
            % self._kv({'category': category, 'header': hexstring(header), 'body': hexstring(body),})
        }
        if negotiated:
            message.update(self._negotiated(negotiated))
        return self._header(
            self._neighbor(neighbor, direction, self._kv(message)),
            '',
            '',
            neighbor,
            message_type=Message.string(category),
        )

    def keepalive(self, neighbor, direction, negotiated, header, body):
        return self._header(self._neighbor(neighbor, direction, ''), header, body, neighbor, message_type='keepalive')

    def open(self, neighbor, direction, message, negotiated, header, body):
        return self._header(
            self._neighbor(
                neighbor,
                direction,
                self._kv(
                    {
                        'open': '{ %s }'
                        % self._kv(
                            {
                                'version': message.version,
                                'asn': message.asn,
                                'hold_time': message.hold_time,
                                'router_id': message.router_id,
                                'capabilities': '{ %s }' % self._json_kv(message.capabilities),
                            }
                        )
                    }
                ),
            ),
            header,
            body,
            neighbor,
            message_type='open',
        )

    def _update(self, update):
        plus = {}
        minus = {}

        # all the next-hops should be the same but let's not assume it

        for nlri in update.nlris:
            nexthop = str(nlri.nexthop) if nlri.nexthop else 'null'
            if nlri.action == IN.ANNOUNCED:  # pylint: disable=E1101
                plus.setdefault(nlri.family(), {}).setdefault(nexthop, []).append(nlri)
            if nlri.action == IN.WITHDRAWN:  # pylint: disable=E1101
                minus.setdefault(nlri.family(), []).append(nlri)

        add = []
        for family in plus:
            s = '"%s %s": { ' % family
            m = ''
            for nexthop in plus[family]:
                nlris = plus[family][nexthop]
                m += '"%s": [ ' % nexthop
                m += ', '.join('%s' % nlri.json(compact=self.compact) for nlri in nlris)
                m += ' ], '
            s += m[:-2]
            s += ' }'
            add.append(s)

        remove = []
        for family in minus:
            nlris = minus[family]
            s = '"%s %s": [ ' % family
            s += ', '.join('%s' % nlri.json(compact=self.compact) for nlri in nlris)
            s += ' ]'
            remove.append(s)

        nlri = ''
        if not add and not remove:
            if update.nlris:  # an EOR
                return {'message': '{ %s }' % update.nlris[0].json()}
        if add:
            nlri += '"announce": { %s }' % ', '.join(add)
        if add and remove:
            nlri += ', '
        if remove:
            nlri += '"withdraw": { %s }' % ', '.join(remove)

        attributes = '' if not update.attributes else '"attribute": { %s }' % update.attributes.json()
        if not attributes or not nlri:
            update = '"update": { %s%s }' % (attributes, nlri)
        else:
            update = '"update": { %s, %s }' % (attributes, nlri)

        return {'message': '{ %s }' % update}

    def update(self, neighbor, direction, update, negotiated, header, body):
        message = self._update(update)
        if negotiated:
            message.update(self._negotiated(negotiated))
        return self._header(
            self._neighbor(neighbor, direction, self._kv(message)), header, body, neighbor, message_type='update'
        )

    def refresh(self, neighbor, direction, refresh, negotiated, header, body):
        return self._header(
            self._neighbor(
                neighbor,
                direction,
                self._kv(
                    {
                        'route-refresh': '{ %s }'
                        % self._kv(
                            {
                                'afi': '"%s"' % refresh.afi,
                                'safi': '"%s"' % refresh.safi,
                                'subtype': '"%s"' % refresh.reserved,
                            }
                        )
                    }
                ),
            ),
            header,
            body,
            neighbor,
            message_type='refresh',
        )

    def _operational_query(self, neighbor, direction, operational, header, body):
        return self._header(
            self._neighbor(
                neighbor,
                direction,
                self._kv(
                    {
                        'operational': '{ %s }'
                        % self._kv(
                            {
                                'name': '"%s"' % operational.name,
                                'afi': '"%s"' % operational.afi,
                                'safi': '"%s"' % operational.safi,
                            }
                        )
                    }
                ),
            ),
            header,
            body,
            neighbor,
            message_type='operational',
        )

    def _operational_advisory(self, neighbor, direction, operational, header, body):
        return self._header(
            self._neighbor(
                neighbor,
                direction,
                self._kv(
                    {
                        'operational': '{ %s }'
                        % self._kv(
                            {
                                'name': '"%s"' % operational.name,
                                'afi': '"%s"' % operational.afi,
                                'safi': '"%s"' % operational.safi,
                                'advisory': '"%s"' % operational.data,
                            }
                        )
                    }
                ),
            ),
            header,
            body,
            neighbor,
            message_type='operational',
        )

    def _operational_counter(self, neighbor, direction, operational, header, body):
        return self._header(
            self._neighbor(
                neighbor,
                direction,
                self._kv(
                    {
                        'operational': '{ %s }'
                        % self._kv(
                            {
                                'name': '"%s"' % operational.name,
                                'afi': '"%s"' % operational.afi,
                                'safi': '"%s"' % operational.safi,
                                'router-id': operational.routerid,
                                'sequence': operational.sequence,
                                'counter': operational.counter,
                            }
                        )
                    }
                ),
            ),
            header,
            body,
            neighbor,
            message_type='operational',
        )

    def operational(self, neighbor, direction, what, operational, negotiated, header, body):
        if what == 'advisory':
            return self._operational_advisory(neighbor, direction, operational, header, body)
        elif what == 'query':
            return self._operational_query(neighbor, direction, operational, header, body)
        elif what == 'counter':
            return self._operational_counter(neighbor, direction, operational, header, body)
        # elif what == 'interface':
        # 	return self._operational_interface(peer,operational)
        else:
            raise RuntimeError('the code is broken, we are trying to print a unknown type of operational message')
