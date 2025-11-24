#!/usr/bin/env python3
"""Response/json.py

Created by Thomas Mangin on 2012-12-30.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import os
import socket
import time

from exabgp.util import hexstring

from exabgp.bgp.message import Message
from exabgp.bgp.message import Action

from exabgp.environment import getenv
from exabgp.bgp.message.open.capability.refresh import REFRESH

from exabgp.reactor.interrupt import Signal


def nop(_):
    return _


class JSON:
    _count: dict[str, int] = {}

    def __init__(self, version):
        self.version = version
        self.time = nop
        self.compact = getenv().api.compact

    # def _reset (self, neighbor):
    #     self._count[neighbor.uid] = 0
    #     return 0

    def _counter(self, neighbor):
        increased = self._count.get(neighbor.uid, 0) + 1
        self._count[neighbor.uid] = increased
        return increased

    def _string(self, object):
        if issubclass(object.__class__, bool):
            return 'true' if object else 'false'
        if issubclass(object.__class__, int):
            return str(object)
        string = str(object)
        if '{' in string:
            return string
        if '[' in string:
            return string
        return f'"{object}"'

    def _header(self, content, header, body, neighbor, message_type=None):
        peer = f'"host" : "{socket.gethostname()}", '
        pid = f'"pid" : {os.getpid()}, '
        ppid = f'"ppid" : {os.getppid()}, '
        counter = f'"counter": {self._counter(neighbor)}, ' if neighbor is not None else ''
        header = f'"header": "{hexstring(header)}", ' if header else ''
        body = f'"body": "{hexstring(body)}", ' if body else ''
        mtype = f'"type": "{message_type}", ' if message_type else 'default'

        return f'{{ "exabgp": "{self.version}", "time": {self.time(time.time())}, {peer}{pid}{ppid}{counter}{mtype}{header}{body}{content} }}'

    def _neighbor(self, neighbor, direction, content):
        local_addr = neighbor['local-address']
        peer_addr = neighbor['peer-address']
        local_as = neighbor['local-as']
        peer_as = neighbor['peer-as']
        sep1 = ', ' if direction else ''
        dir_field = f'"direction": "{direction}"' if direction else ''
        sep2 = ', ' if content else ' '

        return f'"neighbor": {{ "address": {{ "local": "{local_addr}", "peer": "{peer_addr}" }}, "asn": {{ "local": {local_as}, "peer": {peer_as} }} {sep1}{dir_field}{sep2}{content} }}'

    def _kv(self, extra):
        return ', '.join(f'"{k}": {self._string(v)}' for (k, v) in extra.items())

    def _json_kv(self, extra):
        return ', '.join(f'"{k}": {v.json()}' for (k, v) in extra.items())

    def _json_list(self, extra):
        return ', '.join(v.json() for v in extra.items())

    def _minimalkv(self, extra):
        return ', '.join(f'"{k}": {self._string(v)}' for (k, v) in extra.items() if v)

    def up(self, neighbor):
        return self._header(
            self._neighbor(
                neighbor,
                None,
                self._kv(
                    {
                        'state': 'up',
                    },
                ),
            ),
            '',
            '',
            neighbor,
            message_type='state',
        )

    def connected(self, neighbor):
        return self._header(
            self._neighbor(
                neighbor,
                None,
                self._kv(
                    {
                        'state': 'connected',
                    },
                ),
            ),
            '',
            '',
            neighbor,
            message_type='state',
        )

    def down(self, neighbor, reason=''):
        def escape_quote(reason):
            # the {} and [] change is an horrible hack until we generate python objects
            # as otherwise we interpret the string as a list or dict
            return reason.replace('[', '(').replace(']', ')').replace('{', '(').replace('}', ')').replace('"', '\\"')

        return self._header(
            self._neighbor(
                neighbor,
                None,
                self._kv(
                    {
                        'state': 'down',
                        'reason': escape_quote(reason),
                    },
                ),
            ),
            '',
            '',
            neighbor,
            message_type='state',
        )

    def shutdown(self):
        return self._header(
            self._kv(
                {
                    'notification': 'shutdown',
                },
            ),
            '',
            '',
            None,
            message_type='notification',
        )

    def _negotiated(self, negotiated):
        families_str = ' ,'.join([f'{family[0]} {family[1]}' for family in negotiated.families])
        nexthop_str = ' ,'.join([f'{family[0]} {family[1]} {family[2]}' for family in negotiated.nexthop])
        kv_content = self._kv(
            {
                'message_size': negotiated.msg_size,
                'hold_time': negotiated.holdtime,
                'asn4': negotiated.asn4,
                'multisession': negotiated.multisession,
                'operational': negotiated.operational,
                'refresh': REFRESH.json(negotiated.refresh),
                'families': f'[ {families_str} ]',
                'nexthop': f'[ {nexthop_str} ]',
                # NOTE: Do not convert to f-string! The nested % formatting with complex
                # comprehensions and conditional logic is more readable with % formatting.
                'add_path': '{{ "send": {}, "receive": {} }}'.format(
                    '[ {} ]'.format(
                        ', '.join(
                            [
                                '"{} {}"'.format(*family)
                                for family in negotiated.families
                                if negotiated.addpath.send(*family)
                            ]
                        )
                    ),
                    '[ {} ]'.format(
                        ', '.join(
                            [
                                '"{} {}"'.format(*family)
                                for family in negotiated.families
                                if negotiated.addpath.receive(*family)
                            ],
                        )
                    ),
                ),
            },
        )
        return {'negotiated': f'{{ {kv_content} }} '}

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
            self._neighbor(neighbor, None, self._kv({'state': fsm.name()})),
            '',
            '',
            neighbor,
            message_type='fsm',
        )

    def signal(self, neighbor, signal):
        return self._header(
            self._neighbor(
                neighbor,
                None,
                self._kv(
                    {
                        'code': str(signal),
                        'name': Signal.name(signal),
                    },
                ),
            ),
            '',
            '',
            neighbor,
            message_type='signal',
        )

    def notification(self, neighbor, direction, message, negotiated, header, body):
        kv_content = self._kv(
            {
                'code': message.code,
                'subcode': message.subcode,
                'data': hexstring(message.data),
                'message': message.data.decode(),
            },
        )
        return self._header(
            self._neighbor(
                neighbor,
                direction,
                self._kv(
                    {
                        'notification': f'{{ {kv_content} }} ',
                    },
                ),
            ),
            header,
            body,
            neighbor,
            message_type='notification',
        )

    def packets(self, neighbor, direction, category, negotiated, header, body):
        kv_content = self._kv(
            {
                'category': category,
                'header': hexstring(header),
                'body': hexstring(body),
            },
        )
        message = {
            'message': f'{{ {kv_content} }} ',
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
        capabilities_content = self._json_kv(message.capabilities)
        kv_content = self._kv(
            {
                'version': message.version,
                'asn': message.asn,
                'hold_time': message.hold_time,
                'router_id': message.router_id,
                'capabilities': f'{{ {capabilities_content} }}',
            },
        )
        return self._header(
            self._neighbor(
                neighbor,
                direction,
                self._kv(
                    {
                        'open': f'{{ {kv_content} }}',
                    },
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
            try:
                nexthop = str(nlri.nexthop)
            except (AttributeError, TypeError, ValueError):
                nexthop = 'null'
            if nlri.action == Action.ANNOUNCE:  # pylint: disable=E1101
                plus.setdefault(nlri.family().afi_safi(), {}).setdefault(nexthop, []).append(nlri)
            if nlri.action == Action.WITHDRAW:  # pylint: disable=E1101
                minus.setdefault(nlri.family().afi_safi(), []).append(nlri)

        add = []
        for family in plus:
            s = f'"{family[0]} {family[1]}": {{ '
            m = ''
            for nexthop in plus[family]:
                nlris = plus[family][nexthop]
                m += f'"{nexthop}": [ '
                m += ', '.join(nlri.json(compact=self.compact) for nlri in nlris)
                m += ' ], '
            s += m[:-2]
            s += ' }'
            add.append(s)

        remove = []
        for family in minus:
            nlris = minus[family]
            s = f'"{family[0]} {family[1]}": [ '
            s += ', '.join(nlri.json(compact=self.compact) for nlri in nlris)
            s += ' ]'
            remove.append(s)

        nlri = ''
        if not add and not remove:
            if update.nlris:  # an EOR
                return {'message': f'{{ {update.nlris[0].json()} }}'}
        if add:
            add_str = ', '.join(add)
            nlri += f'"announce": {{ {add_str} }}'
        if add and remove:
            nlri += ', '
        if remove:
            remove_str = ', '.join(remove)
            nlri += f'"withdraw": {{ {remove_str} }}'

        attributes = '' if not update.attributes else f'"attribute": {{ {update.attributes.json()} }}'
        if not attributes or not nlri:
            update = f'"update": {{ {attributes}{nlri} }}'
        else:
            update = f'"update": {{ {attributes}, {nlri} }}'

        return {'message': f'{{ {update} }}'}

    def update(self, neighbor, direction, update, negotiated, header, body):
        message = self._update(update)
        if negotiated:
            message.update(self._negotiated(negotiated))
        return self._header(
            self._neighbor(neighbor, direction, self._kv(message)),
            header,
            body,
            neighbor,
            message_type='update',
        )

    def refresh(self, neighbor, direction, refresh, negotiated, header, body):
        kv_content = self._kv(
            {
                'afi': f'"{refresh.afi}"',
                'safi': f'"{refresh.safi}"',
                'subtype': f'"{refresh.reserved}"',
            },
        )
        return self._header(
            self._neighbor(
                neighbor,
                direction,
                self._kv(
                    {
                        'route-refresh': f'{{ {kv_content} }}',
                    },
                ),
            ),
            header,
            body,
            neighbor,
            message_type='refresh',
        )

    def _operational_query(self, neighbor, direction, operational, header, body):
        kv_content = self._kv(
            {
                'name': f'"{operational.name}"',
                'afi': f'"{operational.afi}"',
                'safi': f'"{operational.safi}"',
            },
        )
        return self._header(
            self._neighbor(
                neighbor,
                direction,
                self._kv(
                    {
                        'operational': f'{{ {kv_content} }}',
                    },
                ),
            ),
            header,
            body,
            neighbor,
            message_type='operational',
        )

    def _operational_advisory(self, neighbor, direction, operational, header, body):
        kv_content = self._kv(
            {
                'name': f'"{operational.name}"',
                'afi': f'"{operational.afi}"',
                'safi': f'"{operational.safi}"',
                'advisory': f'"{operational.data}"',
            },
        )
        return self._header(
            self._neighbor(
                neighbor,
                direction,
                self._kv(
                    {
                        'operational': f'{{ {kv_content} }}',
                    },
                ),
            ),
            header,
            body,
            neighbor,
            message_type='operational',
        )

    def _operational_counter(self, neighbor, direction, operational, header, body):
        kv_content = self._kv(
            {
                'name': f'"{operational.name}"',
                'afi': f'"{operational.afi}"',
                'safi': f'"{operational.safi}"',
                'router-id': operational.routerid,
                'sequence': operational.sequence,
                'counter': operational.counter,
            },
        )
        return self._header(
            self._neighbor(
                neighbor,
                direction,
                self._kv(
                    {
                        'operational': f'{{ {kv_content} }}',
                    },
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
        if what == 'query':
            return self._operational_query(neighbor, direction, operational, header, body)
        if what == 'counter':
            return self._operational_counter(neighbor, direction, operational, header, body)
        # elif what == 'interface':
        #     return self._operational_interface(peer,operational)
        raise RuntimeError('the code is broken, we are trying to print a unknown type of operational message')
