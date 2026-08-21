#!/usr/bin/env python3
"""Response/json.py

Created by Thomas Mangin on 2012-12-30.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import json
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


class _RawJSON(str):
    """JSON fragment already encoded by this module."""


class JSON:
    _count = {}

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

    def _safi_display_name(self, afi, safi):
        return str(safi)

    def _string(self, obj):
        if isinstance(obj, _RawJSON):
            return str(obj)
        if issubclass(obj.__class__, bool):
            return 'true' if obj else 'false'
        if issubclass(obj.__class__, int):
            return str(obj)
        return json.dumps(str(obj))

    def _json(self, content):
        return _RawJSON(content)

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
        router_id = neighbor['router-id']
        rid_field = f', "router-id": "{router_id}"' if router_id else ''
        sep1 = ', ' if direction else ''
        dir_field = f'"direction": "{direction}"' if direction else ''
        sep2 = ', ' if content else ' '

        return f'"neighbor": {{ "address": {{ "local": "{local_addr}", "peer": "{peer_addr}" }}, "asn": {{ "local": {local_as}, "peer": {peer_as} }}{rid_field} {sep1}{dir_field}{sep2}{content} }}'

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
        return self._header(
            self._neighbor(
                neighbor,
                None,
                self._kv(
                    {
                        'state': 'down',
                        'reason': reason,
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
        families = [f'{family[0]} {self._safi_display_name(family[0], family[1])}' for family in negotiated.families]
        nexthop = [f'{nh[0]} {self._safi_display_name(nh[0], nh[1])} {nh[2]}' for nh in negotiated.nexthop]
        add_path_send = [
            f'{family[0]} {self._safi_display_name(family[0], family[1])}'
            for family in negotiated.families
            if negotiated.addpath.send(*family)
        ]
        add_path_receive = [
            f'{family[0]} {self._safi_display_name(family[0], family[1])}'
            for family in negotiated.families
            if negotiated.addpath.receive(*family)
        ]
        kv_content = self._kv(
            {
                'message_size': negotiated.msg_size,
                'hold_time': negotiated.holdtime,
                'asn4': negotiated.asn4,
                'multisession': negotiated.multisession,
                'operational': negotiated.operational,
                'refresh': REFRESH.json(negotiated.refresh),
                'families': self._json(json.dumps(families)),
                'nexthop': self._json(json.dumps(nexthop)),
                'add_path': self._json(json.dumps({'send': add_path_send, 'receive': add_path_receive})),
            },
        )
        return {'negotiated': self._json(f'{{ {kv_content} }} ')}

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
                'message': message.data.decode('utf-8', 'replace'),
            },
        )
        return self._header(
            self._neighbor(
                neighbor,
                direction,
                self._kv(
                    {
                        'notification': self._json(f'{{ {kv_content} }} '),
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
        message: dict[str, str] = {
            'message': self._json(f'{{ {kv_content} }} '),
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
                'capabilities': self._json(f'{{ {capabilities_content} }}'),
            },
        )
        return self._header(
            self._neighbor(
                neighbor,
                direction,
                self._kv(
                    {
                        'open': self._json(f'{{ {kv_content} }}'),
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
            except Exception:
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
                return {'message': self._json(f'{{ {update.nlris[0].json()} }}')}
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

        return {'message': self._json(f'{{ {update} }}')}

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
                'afi': str(refresh.afi),
                'safi': str(refresh.safi),
                'subtype': str(refresh.reserved),
            },
        )
        return self._header(
            self._neighbor(
                neighbor,
                direction,
                self._kv(
                    {
                        'route-refresh': self._json(f'{{ {kv_content} }}'),
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
                'name': operational.name,
                'afi': str(operational.afi),
                'safi': str(operational.safi),
            },
        )
        return self._header(
            self._neighbor(
                neighbor,
                direction,
                self._kv(
                    {
                        'operational': self._json(f'{{ {kv_content} }}'),
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
                'name': operational.name,
                'afi': str(operational.afi),
                'safi': str(operational.safi),
                'advisory': operational.data.decode('utf-8', 'replace')
                if isinstance(operational.data, bytes)
                else operational.data,
            },
        )
        return self._header(
            self._neighbor(
                neighbor,
                direction,
                self._kv(
                    {
                        'operational': self._json(f'{{ {kv_content} }}'),
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
                'name': operational.name,
                'afi': str(operational.afi),
                'safi': str(operational.safi),
                'router-id': str(operational.routerid),
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
                        'operational': self._json(f'{{ {kv_content} }}'),
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
