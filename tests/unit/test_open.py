#!/usr/bin/env python3
# encoding: utf-8
"""open.py

Created by Thomas Mangin on 2009-09-06.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

import unittest

from exabgp.protocol.family import AFI
from exabgp.protocol.family import SAFI
from exabgp.bgp.message import Message
from exabgp.bgp.message import Open
from exabgp.bgp.message.open import Version
from exabgp.bgp.message.open import ASN
from exabgp.bgp.message.open import RouterID
from exabgp.bgp.message.open import HoldTime
from exabgp.bgp.message.open.capability import Capabilities
from exabgp.bgp.message.open.capability import Capability
from exabgp.bgp.message.open.capability import RouteRefresh

from exabgp.bgp.message.direction import Direction


open_body = [
    0x4,
    0xFF,
    0xFE,
    0x0,
    0xB4,
    0x0,
    0x0,
    0x0,
    0x0,
    0x20,
    0x2,
    0x6,
    0x1,
    0x4,
    0x0,
    0x1,
    0x0,
    0x1,
    0x2,
    0x6,
    0x1,
    0x4,
    0x0,
    0x2,
    0x0,
    0x1,
    0x2,
    0x2,
    0x80,
    0x0,
    0x2,
    0x2,
    0x2,
    0x0,
    0x2,
    0x6,
    0x41,
    0x4,
    0x0,
    0x0,
    0xFF,
    0xFE,
]


class TestData(unittest.TestCase):
    def test_1_open(self) -> None:
        # this OPEN carries route-refresh twice, under the RFC code and under the code
        # Cisco uses.  Both resolve to the same RouteRefresh class, and the code actually
        # received now lives on the instance rather than on the class, so the expected
        # value for 128 must be unpacked through Capability.unpack() to carry that code.
        # RouteRefresh() alone would hold the declared RFC code and compare unequal to
        # the peer's Cisco one (RouteRefresh equality is ID sensitive, see refresh.py).
        cisco_route_refresh = Capability.unpack(Capability.CODE.ROUTE_REFRESH_CISCO, Capabilities(), b'')
        check_capa = {
            1: [(AFI.ipv4, SAFI.unicast), (AFI.ipv6, SAFI.unicast)],
            2: RouteRefresh(),
            65: 65534,
            128: cisco_route_refresh,
        }

        message_id = 1
        negotiated = {'invalid': 'test'}

        o = Message.unpack(message_id, bytes(open_body), Direction.IN, negotiated)

        self.assertEqual(o.version, 4)
        self.assertEqual(o.asn, 65534)
        self.assertEqual(o.router_id, RouterID('0.0.0.0'))
        self.assertEqual(o.hold_time, 180)
        for k, v in o.capabilities.items():
            self.assertEqual(v, check_capa[k])

    def test_2_open(self) -> None:
        capabilities = Capabilities()
        o = Open(Version(4), ASN(65500), HoldTime(180), RouterID('127.0.0.1'), capabilities)
        self.assertEqual(o.version, 4)
        self.assertEqual(o.asn, 65500)
        self.assertEqual(o.router_id, RouterID('127.0.0.1'))
        self.assertEqual(o.hold_time, 180)
        self.assertEqual(o.capabilities, {})


if __name__ == '__main__':
    unittest.main()
