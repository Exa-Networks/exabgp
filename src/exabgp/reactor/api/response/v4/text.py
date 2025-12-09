"""v4/text.py

API v4 Text encoder - wraps v6 JSON to ensure v6 code is exercised,
then generates text output from source objects.

Created by Thomas Mangin on 2024-12-04.
Copyright (c) 2024 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

from exabgp.util import hexstring
from exabgp.reactor.api.response.json import JSON
from exabgp.version import json as json_version

if TYPE_CHECKING:
    from exabgp.bgp.neighbor import Neighbor
    from exabgp.bgp.message.open.capability.negotiated import Negotiated
    from exabgp.bgp.message.notification import Notification
    from exabgp.bgp.message.open import Open
    from exabgp.bgp.message.update import UpdateCollection
    from exabgp.bgp.message.refresh import RouteRefresh
    from exabgp.bgp.message.operational import OperationalFamily
    from exabgp.bgp.fsm import FSM


class V4Text:
    """API v4 Text encoder - wraps v6 JSON for testing, outputs text.

    This class calls the v6 JSON encoder internally to ensure all v4 text
    calls exercise the v6 code path. The JSON result is discarded and text
    output is generated directly from the source objects.

    This ensures:
    - All v4 tests implicitly test v6 (via the internal JSON call)
    - Text output maintains the same format as the original Text encoder
    """

    def __init__(self, version: str) -> None:
        self._v6 = JSON(json_version)  # Delegate to v6 encoder (for testing)
        self.version = version

    def _header_body(self, header: bytes, body: bytes) -> str:
        header_str = f' header {hexstring(header)}' if header else ''
        body_str = f' body {hexstring(body)}' if body else ''
        total_string = header_str + body_str if body_str else header_str
        return total_string

    def up(self, neighbor: 'Neighbor') -> str:
        # Call v6 to ensure it's tested, then discard result
        _ = self._v6.up(neighbor)
        return f'neighbor {neighbor.session.peer_address} up\n'

    def connected(self, neighbor: 'Neighbor') -> str:
        _ = self._v6.connected(neighbor)
        return f'neighbor {neighbor.session.peer_address} connected\n'

    def down(self, neighbor: 'Neighbor', reason: str = '') -> str:
        _ = self._v6.down(neighbor, reason)
        return f'neighbor {neighbor.session.peer_address} down - {reason}\n'

    def shutdown(self) -> str:
        _ = self._v6.shutdown()
        return f'shutdown {os.getpid()} {os.getppid()}\n'

    def negotiated(self, neighbor: 'Neighbor', negotiated: 'Negotiated') -> None:
        # Call v6, but text format doesn't output negotiated info
        _ = self._v6.negotiated(neighbor, negotiated)
        return None

    def fsm(self, neighbor: 'Neighbor', fsm: 'FSM') -> None:
        # Call v6, but text format doesn't output FSM info
        _ = self._v6.fsm(neighbor, fsm)
        return None

    def signal(self, neighbor: 'Neighbor', signal: int) -> None:
        # Call v6, but text format doesn't output signal info
        _ = self._v6.signal(neighbor, signal)
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
        _ = self._v6.notification(neighbor, direction, message, header, body, negotiated)
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
        _ = self._v6.packets(neighbor, direction, category, header, body, negotiated)
        return f'neighbor {neighbor.session.peer_address} {direction} {category}{self._header_body(header, body)}\n'

    def keepalive(
        self, neighbor: 'Neighbor', direction: str, header: bytes, body: bytes, negotiated: 'Negotiated'
    ) -> str:
        _ = self._v6.keepalive(neighbor, direction, header, body, negotiated)
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
        _ = self._v6.open(neighbor, direction, sent_open, header, body, negotiated)
        capabilities_str = str(sent_open.capabilities).lower()
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
        _ = self._v6.update(neighbor, direction, update, header, body, negotiated)

        prefix = f'neighbor {neighbor.session.peer_address} {direction} update'
        r = f'{prefix} start\n'

        attributes = str(update.attributes)

        # EOR messages have .nlris directly but no .announces/.withdraws
        if getattr(update, 'EOR', False):
            for nlri in update.nlris:  # type: ignore[union-attr]
                r += f'{prefix} route {nlri.extensive()}\n'
        else:
            # Process announces - get nexthop from RoutedNLRI container
            for routed in update.announces:
                nlri = routed.nlri
                nexthop = routed.nexthop
                if nexthop:
                    r += f'{prefix} announced {nlri.extensive()}{attributes}\n'
                else:
                    # Flow or other routes without nexthop
                    r += f'{prefix} {nlri.extensive()} {attributes}\n'

            # Process withdraws
            for nlri in update.withdraws:
                r += f'{prefix} withdrawn {nlri.extensive()}\n'

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
        _ = self._v6.refresh(neighbor, direction, refresh, header, body, negotiated)
        return f'neighbor {neighbor.session.peer_address} {direction} route-refresh afi {refresh.afi} safi {refresh.safi} {refresh.reserved}{self._header_body(header, body)}\n'

    def _operational_advisory(
        self, neighbor: 'Neighbor', direction: str, operational: 'OperationalFamily', header: bytes, body: bytes
    ) -> str:
        data = operational.data.decode('utf-8') if isinstance(operational.data, bytes) else operational.data
        return f'neighbor {neighbor.session.peer_address} {direction} operational {operational.name} afi {operational.afi} safi {operational.safi} advisory "{data}"{self._header_body(header, body)}'

    def _operational_query(
        self, neighbor: 'Neighbor', direction: str, operational: 'OperationalFamily', header: bytes, body: bytes
    ) -> str:
        return f'neighbor {neighbor.session.peer_address} {direction} operational {operational.name} afi {operational.afi} safi {operational.safi}{self._header_body(header, body)}'

    def _operational_counter(
        self, neighbor: 'Neighbor', direction: str, operational: Any, header: bytes, body: bytes
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
        # Call v6 first to ensure it's tested
        _ = self._v6.operational(neighbor, direction, what, operational, header, body, negotiated)

        if what == 'advisory':
            return self._operational_advisory(neighbor, direction, operational, header, body)
        if what == 'query':
            return self._operational_query(neighbor, direction, operational, header, body)
        if what == 'counter':
            return self._operational_counter(neighbor, direction, operational, header, body)
        raise RuntimeError('the code is broken, we are trying to print a unknown type of operational message')
