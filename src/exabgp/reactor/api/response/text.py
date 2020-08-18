#!/usr/bin/env python
# encoding: utf-8
"""
response/text.py

Created by Thomas Mangin on 2012-12-30.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

import os

from exabgp.util import hexstring
from exabgp.bgp.message import IN


class Text(object):
    def __init__(self, version):
        self.version = version

    def _header_body(self, header, body):
        header = ' header %s' % hexstring(header) if header else ''
        body = ' body %s' % hexstring(body) if body else ''

        total_string = header + body if body else header

        return total_string

    def _counter(self, neighbor):
        return None

    def up(self, neighbor):
        return 'neighbor %s up\n' % (neighbor.peer_address)

    def connected(self, neighbor):
        return 'neighbor %s connected\n' % (neighbor.peer_address)

    def down(self, neighbor, reason=''):
        return 'neighbor %s down - %s\n' % (neighbor.peer_address, reason)

    def shutdown(self):
        return 'shutdown %d %d\n' % (os.getpid(), os.getppid())

    def negotiated(self, neighbor, negotiated):
        return None

    def fsm(self, neighbor, fsm):
        return None

    def signal(self, neighbor, signal):
        return None

    def notification(self, neighbor, direction, message, negotiated, header, body):
        return 'neighbor %s %s notification code %d subcode %d data %s%s\n' % (
            neighbor.peer_address,
            direction,
            message.code,
            message.subcode,
            hexstring(message.data),
            self._header_body(header, body),
        )

    def packets(self, neighbor, direction, category, negotiated, header, body):
        return 'neighbor %s %s %d%s\n' % (neighbor.peer_address, direction, category, self._header_body(header, body))

    def keepalive(self, neighbor, direction, negotiated, header, body):
        return 'neighbor %s %s keepalive%s\n' % (neighbor.peer_address, direction, self._header_body(header, body))

    def open(self, neighbor, direction, sent_open, negotiated, header, body):
        return 'neighbor %s %s open version %d asn %d hold_time %s router_id %s capabilities [%s]%s\n' % (
            neighbor.peer_address,
            direction,
            sent_open.version,
            sent_open.asn,
            sent_open.hold_time,
            sent_open.router_id,
            str(sent_open.capabilities).lower(),
            self._header_body(header, body),
        )

    def update(self, neighbor, direction, update, negotiated, header, body):
        prefix = 'neighbor %s %s update' % (neighbor.peer_address, direction,)

        r = '%s start\n' % prefix

        attributes = str(update.attributes)
        for nlri in update.nlris:
            if nlri.EOR:
                r += '%s route %s\n' % (prefix, nlri.extensive())
            elif nlri.action == IN.ANNOUNCED:  # pylint: disable=E1101
                if nlri.nexthop:
                    r += '%s announced %s%s\n' % (prefix, nlri.extensive(), attributes)
                else:
                    # This is an EOR or Flow or ... something newer
                    r += '%s %s %s\n' % (prefix, nlri.extensive(), attributes)
            else:
                r += '%s withdrawn %s\n' % (prefix, nlri.extensive())
        if header or body:
            r += '%s\n' % self._header_body(header, body)

        r += '%s end\n' % prefix

        return r

    def refresh(self, neighbor, direction, refresh, negotiated, header, body):
        return 'neighbor %s %s route-refresh afi %s safi %s %s%s\n' % (
            neighbor.peer_address,
            direction,
            refresh.afi,
            refresh.safi,
            refresh.reserved,
            self._header_body(header, body),
        )

    def _operational_advisory(self, neighbor, direction, operational, header, body):
        return 'neighbor %s %s operational %s afi %s safi %s advisory "%s"%s' % (
            neighbor.peer_address,
            direction,
            operational.name,
            operational.afi,
            operational.safi,
            operational.data,
            self._header_body(header, body),
        )

    def _operational_query(self, neighbor, direction, operational, header, body):
        return 'neighbor %s %s operational %s afi %s safi %s%s' % (
            neighbor.peer_address,
            direction,
            operational.name,
            operational.afi,
            operational.safi,
            self._header_body(header, body),
        )

    def _operational_counter(self, neighbor, direction, operational, header, body):
        return 'neighbor %s %s operational %s afi %s safi %s router-id %s sequence %d counter %d%s' % (
            neighbor.peer_address,
            direction,
            operational.name,
            operational.afi,
            operational.safi,
            operational.routerid,
            operational.sequence,
            operational.counter,
            self._header_body(header, body),
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
