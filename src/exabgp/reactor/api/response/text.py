#!/usr/bin/env python3
"""response/text.py

Created by Thomas Mangin on 2012-12-30.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import os

from exabgp.util import hexstring
from exabgp.bgp.message import Action


class Text:
    def __init__(self, version):
        self.version = version

    def _header_body(self, header, body):
        header = f' header {hexstring(header)}' if header else ''
        body = f' body {hexstring(body)}' if body else ''

        total_string = header + body if body else header

        return total_string

    def _counter(self, neighbor):
        return None

    def up(self, neighbor):
        return f'neighbor {neighbor.peer_address} up\n'

    def connected(self, neighbor):
        return f'neighbor {neighbor.peer_address} connected\n'

    def down(self, neighbor, reason=''):
        return f'neighbor {neighbor.peer_address} down - {reason}\n'

    def shutdown(self):
        return f'shutdown {os.getpid()} {os.getppid()}\n'

    def negotiated(self, neighbor, negotiated):
        return None

    def fsm(self, neighbor, fsm):
        return None

    def signal(self, neighbor, signal):
        return None

    def notification(self, neighbor, direction, message, header, body, negotiated=None):
        data_hex = hexstring(message.data)
        header_body = self._header_body(header, body)
        return f'neighbor {neighbor.peer_address} {direction} notification code {message.code} subcode {message.subcode} data {data_hex}{header_body}\n'

    def packets(self, neighbor, direction, category, negotiated, header, body):
        return f'neighbor {neighbor.peer_address} {direction} {category}{self._header_body(header, body)}\n'

    def keepalive(self, neighbor, direction, negotiated, header, body):
        return f'neighbor {neighbor.peer_address} {direction} keepalive{self._header_body(header, body)}\n'

    def open(self, neighbor, direction, sent_open, negotiated, header, body):
        capabilities_str = str(sent_open.capabilities).lower()
        header_body = self._header_body(header, body)
        return f'neighbor {neighbor.peer_address} {direction} open version {sent_open.version} asn {sent_open.asn} hold_time {sent_open.hold_time} router_id {sent_open.router_id} capabilities [{capabilities_str}]{header_body}\n'

    def update(self, neighbor, direction, update, negotiated, header, body):
        prefix = f'neighbor {neighbor.peer_address} {direction} update'

        r = f'{prefix} start\n'

        attributes = str(update.attributes)
        for nlri in update.nlris:
            if nlri.EOR:
                r += f'{prefix} route {nlri.extensive()}\n'
            elif nlri.action == Action.ANNOUNCE:  # pylint: disable=E1101
                if nlri.nexthop:
                    r += f'{prefix} announced {nlri.extensive()}{attributes}\n'
                else:
                    # This is an EOR or Flow or ... something newer
                    r += f'{prefix} {nlri.extensive()} {attributes}\n'
            else:
                r += f'{prefix} withdrawn {nlri.extensive()}\n'
        if header or body:
            r += f'{self._header_body(header, body)}\n'

        r += f'{prefix} end\n'

        return r

    def refresh(self, neighbor, direction, refresh, negotiated, header, body):
        return f'neighbor {neighbor.peer_address} {direction} route-refresh afi {refresh.afi} safi {refresh.safi} {refresh.reserved}{self._header_body(header, body)}\n'

    def _operational_advisory(self, neighbor, direction, operational, header, body):
        return f'neighbor {neighbor.peer_address} {direction} operational {operational.name} afi {operational.afi} safi {operational.safi} advisory "{operational.data}"{self._header_body(header, body)}'

    def _operational_query(self, neighbor, direction, operational, header, body):
        return f'neighbor {neighbor.peer_address} {direction} operational {operational.name} afi {operational.afi} safi {operational.safi}{self._header_body(header, body)}'

    def _operational_counter(self, neighbor, direction, operational, header, body):
        return f'neighbor {neighbor.peer_address} {direction} operational {operational.name} afi {operational.afi} safi {operational.safi} router-id {operational.routerid} sequence {operational.sequence} counter {operational.counter}{self._header_body(header, body)}'

    def operational(self, neighbor, direction, what, operational, negotiated, header, body):
        if what == 'advisory':
            return self._operational_advisory(neighbor, direction, operational, header, body)
        if what == 'query':
            return self._operational_query(neighbor, direction, operational, header, body)
        if what == 'counter':
            return self._operational_counter(neighbor, direction, operational, header, body)
        # elif what == 'interface':
        # 	return self._operational_interface(peer,operational)
        raise RuntimeError('the code is broken, we are trying to print a unknown type of operational message')
