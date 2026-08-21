#!/usr/bin/env python3
"""response/text.py

Created by Thomas Mangin on 2012-12-30.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from exabgp.util import hexstring

if TYPE_CHECKING:
    from typing import Any
    from exabgp.bgp.neighbor import Neighbor
    from exabgp.bgp.message.open.capability.negotiated import Negotiated
    from exabgp.bgp.message.notification import Notification
    from exabgp.bgp.message.open import Open
    from exabgp.bgp.message.update import UpdateCollection
    from exabgp.bgp.message.refresh import RouteRefresh
    from exabgp.bgp.message.operational import OperationalFamily
    from exabgp.bgp.fsm import FSM


def oneline(value: object) -> str:
    """Render a value which a peer may have chosen, without letting it end the line.

    The text API is one event per line, so a consumer splits the stream on newlines.  A
    peer supplied string carrying \\r or \\n therefore forges a whole event: a hostname of
    `a\\nneighbor 1.2.3.4 down - forged` made the reader see a session go down which never
    did.  That is the CWE-116 of GHSA-jcrv-p53f-v5w5 against the other encoder, which the
    advisory did not cover.

    Control characters are escaped rather than dropped, so what the peer sent is still
    visible to whoever is reading, and still only one line.
    """
    text = str(value)
    return ''.join(
        character if character.isprintable() or character == ' ' else repr(character)[1:-1] for character in text
    )


class Text:
    def __init__(self, version: str) -> None:
        self.version = version

    def _header_body(self, header: bytes, body: bytes) -> str:
        header_str = f' header {hexstring(header)}' if header else ''
        body_str = f' body {hexstring(body)}' if body else ''

        total_string = header_str + body_str if body_str else header_str

        return total_string

    def _counter(self, neighbor: 'Neighbor') -> None:
        return None

    def up(self, neighbor: 'Neighbor') -> str:
        return f'neighbor {neighbor.session.peer_address} up\n'

    def connected(self, neighbor: 'Neighbor') -> str:
        return f'neighbor {neighbor.session.peer_address} connected\n'

    def down(self, neighbor: 'Neighbor', reason: str = '') -> str:
        return f'neighbor {neighbor.session.peer_address} down - {oneline(reason)}\n'

    def shutdown(self) -> str:
        return f'shutdown {os.getpid()} {os.getppid()}\n'

    def negotiated(self, neighbor: 'Neighbor', negotiated: 'Negotiated') -> None:
        return None

    def fsm(self, neighbor: 'Neighbor', fsm: 'FSM') -> None:
        return None

    def signal(self, neighbor: 'Neighbor', signal: int) -> None:
        return None

    def notification(
        self,
        neighbor: 'Neighbor',
        direction: str,
        message: 'Notification',
        header: bytes,
        body: bytes,
        negotiated: 'Negotiated',
    ) -> str:
        data_hex = hexstring(message.data)
        header_body = self._header_body(header, body)
        return f'neighbor {neighbor.session.peer_address} {direction} notification code {message.code} subcode {message.subcode} data {data_hex}{header_body}\n'

    def packets(
        self,
        neighbor: 'Neighbor',
        direction: str,
        category: int,
        header: bytes,
        body: bytes,
        negotiated: 'Negotiated',
    ) -> str:
        return f'neighbor {neighbor.session.peer_address} {direction} {category}{self._header_body(header, body)}\n'

    def keepalive(
        self, neighbor: 'Neighbor', direction: str, header: bytes, body: bytes, negotiated: 'Negotiated'
    ) -> str:
        return f'neighbor {neighbor.session.peer_address} {direction} keepalive{self._header_body(header, body)}\n'

    def open(
        self,
        neighbor: 'Neighbor',
        direction: str,
        sent_open: 'Open',
        header: bytes,
        body: bytes,
        negotiated: 'Negotiated',
    ) -> str:
        # the capabilities hold the peer's hostname and software version, free text it chose
        capabilities_str = oneline(str(sent_open.capabilities).lower())
        header_body = self._header_body(header, body)
        return f'neighbor {neighbor.session.peer_address} {direction} open version {sent_open.version} asn {sent_open.asn} hold_time {sent_open.hold_time} router_id {sent_open.router_id} capabilities [{capabilities_str}]{header_body}\n'

    def update(
        self,
        neighbor: 'Neighbor',
        direction: str,
        update: 'UpdateCollection',
        header: bytes,
        body: bytes,
        negotiated: 'Negotiated',
    ) -> str:
        prefix = f'neighbor {neighbor.session.peer_address} {direction} update'

        r = f'{prefix} start\n'

        attributes = str(update.attributes)

        # EOR messages have .nlris directly but no .announces/.withdraws
        if getattr(update, 'IS_EOR', False):
            for nlri in update.nlris:
                r += f'{prefix} route {oneline(nlri.extensive())}\n'
        else:
            # Process announces - get nexthop from RoutedNLRI container
            for routed in update.announces:
                nlri = routed.nlri
                nexthop = routed.nexthop
                nexthop_str = f' next-hop {nexthop}' if nexthop else ''
                r += f'{prefix} announced {oneline(nlri.extensive())}{nexthop_str}{oneline(attributes)}\n'

            # Process withdraws
            for nlri in update.withdraws:
                r += f'{prefix} withdrawn {oneline(nlri.extensive())}\n'

        if header or body:
            r += f'{self._header_body(header, body)}\n'

        r += f'{prefix} end\n'

        return r

    def refresh(
        self,
        neighbor: 'Neighbor',
        direction: str,
        refresh: 'RouteRefresh',
        header: bytes,
        body: bytes,
        negotiated: 'Negotiated',
    ) -> str:
        return f'neighbor {neighbor.session.peer_address} {direction} route-refresh afi {refresh.afi} safi {refresh.safi} {refresh.reserved}{self._header_body(header, body)}\n'

    def _operational_advisory(
        self, neighbor: 'Neighbor', direction: str, operational: 'OperationalFamily', header: bytes, body: bytes
    ) -> str:
        # free text the peer chose, and not promised to be UTF-8
        raw = operational.data
        data = bytes(raw).decode('utf-8', 'replace') if isinstance(raw, (bytes, bytearray, memoryview)) else raw
        return f'neighbor {neighbor.session.peer_address} {direction} operational {operational.name} afi {operational.afi} safi {operational.safi} advisory "{oneline(data)}"{self._header_body(header, body)}'

    def _operational_query(
        self, neighbor: 'Neighbor', direction: str, operational: 'OperationalFamily', header: bytes, body: bytes
    ) -> str:
        return f'neighbor {neighbor.session.peer_address} {direction} operational {operational.name} afi {operational.afi} safi {operational.safi}{self._header_body(header, body)}'

    def _operational_counter(
        self, neighbor: 'Neighbor', direction: str, operational: 'Any', header: bytes, body: bytes
    ) -> str:
        return f'neighbor {neighbor.session.peer_address} {direction} operational {operational.name} afi {operational.afi} safi {operational.safi} router-id {operational.routerid} sequence {operational.sequence} counter {operational.counter}{self._header_body(header, body)}'

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
        # 	return self._operational_interface(peer,operational)
        # a peer choosing an unregistered type arrives here with category 'unknown'
        data = hexstring(bytes(getattr(operational, 'data', b'')))
        return f'neighbor {neighbor.session.peer_address} {direction} operational {operational.name} type {operational.what} data {data}{self._header_body(header, body)}'
