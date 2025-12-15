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
from typing import Any, Callable, TYPE_CHECKING

from exabgp.util import hexstring

from exabgp.bgp.message import Message

from exabgp.environment import getenv
from exabgp.bgp.message.open.capability.refresh import REFRESH
from exabgp.bgp.message.open.capability.negotiated import Negotiated

from exabgp.reactor.interrupt import Signal
from exabgp.protocol.ip import IP

if TYPE_CHECKING:
    from exabgp.bgp.neighbor import Neighbor
    from exabgp.bgp.message.notification import Notification
    from exabgp.bgp.message.open import Open
    from exabgp.bgp.message.update import UpdateCollection
    from exabgp.bgp.message.refresh import RouteRefresh
    from exabgp.bgp.message.operational import OperationalFamily
    from exabgp.bgp.fsm import FSM


def nop(_: float) -> float:
    return _


class JSON:
    _count: dict[str, int] = {}

    def __init__(self, version: str) -> None:
        self.version = version
        self.time: Callable[[float], float] = nop
        self.compact = getenv().api.compact
        self.use_v4_json = False  # Set True for API v4 backward compat
        self.generic_attribute_format = False  # Output generic attributes as hex

    # def _reset (self, neighbor):
    #     self._count[neighbor.uid] = 0
    #     return 0

    def _counter(self, neighbor: 'Neighbor') -> int:
        increased = self._count.get(neighbor.uid, 0) + 1
        self._count[neighbor.uid] = increased
        return increased

    def _string(self, obj: Any) -> str:
        if issubclass(obj.__class__, bool):
            return 'true' if obj else 'false'
        if issubclass(obj.__class__, int):
            return str(obj)
        string = str(obj)
        if '{' in string:
            return string
        if '[' in string:
            return string
        return f'"{obj}"'

    def _header(
        self,
        content: str,
        header: bytes,
        body: bytes,
        neighbor: 'Neighbor | None',
        message_type: str | None = None,
    ) -> str:
        peer = f'"host" : "{socket.gethostname()}", '
        pid = f'"pid" : {os.getpid()}, '
        ppid = f'"ppid" : {os.getppid()}, '
        counter = f'"counter": {self._counter(neighbor)}, ' if neighbor is not None else ''
        header_str = f'"header": "{hexstring(header)}", ' if header else ''
        body_str = f'"body": "{hexstring(body)}", ' if body else ''
        mtype = f'"type": "{message_type}", ' if message_type else 'default'

        return f'{{ "exabgp": "{self.version}", "time": {self.time(time.time())}, {peer}{pid}{ppid}{counter}{mtype}{header_str}{body_str}{content} }}'

    def _neighbor(self, neighbor: 'Neighbor', direction: str | None, content: str) -> str:
        local_addr = neighbor.session.local_address
        peer_addr = neighbor.session.peer_address
        local_as = neighbor.session.local_as
        peer_as = neighbor.session.peer_as
        sep1 = ', ' if direction else ''
        dir_field = f'"direction": "{direction}"' if direction else ''
        sep2 = ', ' if content else ' '

        return f'"neighbor": {{ "address": {{ "local": "{local_addr}", "peer": "{peer_addr}" }}, "asn": {{ "local": {local_as}, "peer": {peer_as} }} {sep1}{dir_field}{sep2}{content} }}'

    def _kv(self, extra: dict[str, Any]) -> str:
        return ', '.join(f'"{k}": {self._string(v)}' for (k, v) in extra.items())

    def _json_kv(self, extra: dict[Any, Any]) -> str:
        return ', '.join(f'"{k}": {v.json()}' for (k, v) in extra.items())

    def _json_list(self, extra: dict[str, Any]) -> str:
        return ', '.join(v.json() for v in extra.values())

    def _minimalkv(self, extra: dict[str, Any]) -> str:
        return ', '.join(f'"{k}": {self._string(v)}' for (k, v) in extra.items() if v)

    def up(self, neighbor: 'Neighbor') -> str:
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
            b'',
            b'',
            neighbor,
            message_type='state',
        )

    def connected(self, neighbor: 'Neighbor') -> str:
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
            b'',
            b'',
            neighbor,
            message_type='state',
        )

    def down(self, neighbor: 'Neighbor', reason: str = '') -> str:
        def escape_quote(reason: str) -> str:
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
            b'',
            b'',
            neighbor,
            message_type='state',
        )

    def shutdown(self) -> str:
        return self._header(
            self._kv(
                {
                    'notification': 'shutdown',
                },
            ),
            b'',
            b'',
            None,
            message_type='notification',
        )

    def _negotiated(self, negotiated: 'Negotiated') -> dict[str, str]:
        families_str = ' ,'.join([f'{family[0]} {family[1]}' for family in negotiated.families])
        # nexthop is list[tuple[AFI, SAFI, AFI]] per RFC5549 - third element is nexthop AFI
        nexthop_str = ' ,'.join([f'{nh[0]} {nh[1]} {nh[2]}' for nh in negotiated.nexthop])
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

    def negotiated(self, neighbor: 'Neighbor', negotiated: 'Negotiated') -> str:
        return self._header(
            self._neighbor(neighbor, None, self._kv(self._negotiated(negotiated))),
            b'',
            b'',
            neighbor,
            message_type='negotiated',
        )

    def fsm(self, neighbor: 'Neighbor', fsm: 'FSM') -> str:
        return self._header(
            self._neighbor(neighbor, None, self._kv({'state': fsm.name()})),
            b'',
            b'',
            neighbor,
            message_type='fsm',
        )

    def signal(self, neighbor: 'Neighbor', signal: int) -> str:
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
            b'',
            b'',
            neighbor,
            message_type='signal',
        )

    def notification(
        self,
        neighbor: 'Neighbor',
        direction: str,
        message: 'Notification',
        header: bytes,
        body: bytes,
        negotiated: 'Negotiated',
    ) -> str:
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

    def packets(
        self,
        neighbor: 'Neighbor',
        direction: str,
        category: int,
        header: bytes,
        body: bytes,
        negotiated: 'Negotiated',
    ) -> str:
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
        if negotiated is not Negotiated.UNSET:
            message.update(self._negotiated(negotiated))
        return self._header(
            self._neighbor(neighbor, direction, self._kv(message)),
            b'',
            b'',
            neighbor,
            message_type=Message.string(category),
        )

    def keepalive(
        self, neighbor: 'Neighbor', direction: str, header: bytes, body: bytes, negotiated: 'Negotiated'
    ) -> str:
        return self._header(self._neighbor(neighbor, direction, ''), header, body, neighbor, message_type='keepalive')

    def open(
        self,
        neighbor: 'Neighbor',
        direction: str,
        message: 'Open',
        header: bytes,
        body: bytes,
        negotiated: 'Negotiated',
    ) -> str:
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

    def _nlri_to_json(self, nlri: Any, nexthop: IP | None = None) -> str:
        """Convert NLRI to JSON string. Uses v4_json() for backward compat if enabled.

        Args:
            nlri: The NLRI object
            nexthop: Optional nexthop IP (passed to v4_json for backward compatibility)
        """
        if self.use_v4_json:
            return nlri.v4_json(compact=self.compact, nexthop=nexthop)
        return nlri.json(compact=self.compact)

    def _update(self, update_msg: 'UpdateCollection') -> dict[str, str]:
        # plus stores: family -> nexthop_string -> list of (nlri, nexthop_ip) tuples
        plus: dict[tuple[Any, Any], dict[str, list[tuple[Any, IP]]]] = {}
        minus: dict[tuple[Any, Any], list[Any]] = {}

        # EOR messages have .nlris directly but no .announces/.withdraws
        if getattr(update_msg, 'EOR', False):
            # EOR message - use .nlris directly with original behavior
            for nlri in update_msg.nlris:  # type: ignore[union-attr]
                nexthop_ip = getattr(nlri, 'nexthop', IP.NoNextHop)
                nexthop_str = str(nexthop_ip) if nexthop_ip is not IP.NoNextHop else 'null'
                plus.setdefault(nlri.family().afi_safi(), {}).setdefault(nexthop_str, []).append((nlri, nexthop_ip))
        else:
            # UpdateCollection - get nexthop from RoutedNLRI container
            for routed in update_msg.announces:
                nlri = routed.nlri
                nexthop_ip = routed.nexthop
                nexthop_str = str(nexthop_ip)
                plus.setdefault(nlri.family().afi_safi(), {}).setdefault(nexthop_str, []).append((nlri, nexthop_ip))

            # Process withdraws - no nexthop needed
            for nlri in update_msg.withdraws:
                minus.setdefault(nlri.family().afi_safi(), []).append(nlri)

        add = []
        for family in plus:
            s = f'"{family[0]} {family[1]}": {{ '
            m = ''
            for nexthop_str in plus[family]:
                nlri_tuples = plus[family][nexthop_str]
                m += f'"{nexthop_str}": [ '
                m += ', '.join(self._nlri_to_json(nlri, nexthop_ip) for nlri, nexthop_ip in nlri_tuples)
                m += ' ], '
            s += m[:-2]
            s += ' }'
            add.append(s)

        remove = []
        for family in minus:
            nlris = minus[family]
            s = f'"{family[0]} {family[1]}": [ '
            s += ', '.join(self._nlri_to_json(nlri) for nlri in nlris)
            s += ' ]'
            remove.append(s)

        nlri_str = ''
        if not add and not remove:
            if update_msg.nlris:  # an EOR
                return {'message': f'{{ {self._nlri_to_json(update_msg.nlris[0])} }}'}
        if add:
            add_str = ', '.join(add)
            nlri_str += f'"announce": {{ {add_str} }}'
        if add and remove:
            nlri_str += ', '
        if remove:
            remove_str = ', '.join(remove)
            nlri_str += f'"withdraw": {{ {remove_str} }}'

        # Include NEXT_HOP in attributes when withdraws present (it's not shown with NLRI for withdraws)
        include_nexthop = bool(minus)
        attributes = (
            ''
            if not update_msg.attributes
            else f'"attribute": {{ {update_msg.attributes.json(include_nexthop=include_nexthop, generic=self.generic_attribute_format)} }}'
        )
        if not attributes or not nlri_str:
            update_str = f'"update": {{ {attributes}{nlri_str} }}'
        else:
            update_str = f'"update": {{ {attributes}, {nlri_str} }}'

        return {'message': f'{{ {update_str} }}'}

    def update(
        self,
        neighbor: 'Neighbor',
        direction: str,
        update: 'UpdateCollection',
        header: bytes,
        body: bytes,
        negotiated: 'Negotiated',
    ) -> str:
        message = self._update(update)
        if negotiated is not Negotiated.UNSET:
            message.update(self._negotiated(negotiated))
        return self._header(
            self._neighbor(neighbor, direction, self._kv(message)),
            header,
            body,
            neighbor,
            message_type='update',
        )

    def refresh(
        self,
        neighbor: 'Neighbor',
        direction: str,
        refresh: 'RouteRefresh',
        header: bytes,
        body: bytes,
        negotiated: 'Negotiated',
    ) -> str:
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

    def _operational_query(
        self, neighbor: 'Neighbor', direction: str, operational: 'OperationalFamily', header: bytes, body: bytes
    ) -> str:
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

    def _operational_advisory(
        self, neighbor: 'Neighbor', direction: str, operational: 'OperationalFamily', header: bytes, body: bytes
    ) -> str:
        data = operational.data.decode('utf-8') if isinstance(operational.data, bytes) else operational.data
        kv_content = self._kv(
            {
                'name': f'"{operational.name}"',
                'afi': f'"{operational.afi}"',
                'safi': f'"{operational.safi}"',
                'advisory': f'"{data}"',
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

    def _operational_counter(
        self, neighbor: 'Neighbor', direction: str, operational: Any, header: bytes, body: bytes
    ) -> str:
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

    def operational(
        self,
        neighbor: 'Neighbor',
        direction: str,
        what: str,
        operational: 'OperationalFamily',
        header: bytes,
        body: bytes,
        negotiated: 'Negotiated',
    ) -> str:
        if what == 'advisory':
            return self._operational_advisory(neighbor, direction, operational, header, body)
        if what == 'query':
            return self._operational_query(neighbor, direction, operational, header, body)
        if what == 'counter':
            return self._operational_counter(neighbor, direction, operational, header, body)
        # elif what == 'interface':
        #     return self._operational_interface(peer,operational)
        raise RuntimeError('the code is broken, we are trying to print a unknown type of operational message')
