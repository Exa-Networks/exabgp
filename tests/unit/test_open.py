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
from exabgp.bgp.message.open.capability.negotiated import Negotiated


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
        # 2 is the RFC route-refresh code (0x02); a bare RouteRefresh() carries
        # that ID as its class-level default. 128 is the Cisco code (0x80): it
        # must be unpacked through Capability.unpack() to carry that ID on the
        # instance, or it would compare unequal to the peer's actual Cisco
        # capability (RouteRefresh equality is ID-sensitive; see refresh.py).
        cisco_route_refresh = Capability.unpack(Capability.CODE.ROUTE_REFRESH_CISCO, Capabilities(), b'')
        check_capa = {
            1: [(AFI.ipv4, SAFI.unicast), (AFI.ipv6, SAFI.unicast)],
            2: RouteRefresh(),
            65: 65534,
            128: cisco_route_refresh,
        }

        message_id = 1
        negotiated = Negotiated.UNSET

        o = Message.unpack(Message.CODE.of(message_id), bytes(open_body), negotiated)

        self.assertEqual(o.version, 4)
        self.assertEqual(o.asn, 65534)
        self.assertEqual(o.router_id, RouterID('0.0.0.0'))
        self.assertEqual(o.hold_time, 180)
        for k, v in o.capabilities.items():
            self.assertEqual(v, check_capa[k])

    def test_2_open(self) -> None:
        capabilities = Capabilities()
        o = Open.make_open(Version(4), ASN(65500), HoldTime(180), RouterID('127.0.0.1'), capabilities)
        self.assertEqual(o.version, 4)
        self.assertEqual(o.asn, 65500)
        self.assertEqual(o.router_id, RouterID('127.0.0.1'))
        self.assertEqual(o.hold_time, 180)
        self.assertEqual(o.capabilities, {})

    def test_router_id_from_string_in_open(self) -> None:
        router_id: RouterID = RouterID.from_string('192.0.2.1')
        self.assertIs(type(router_id), RouterID)
        message = Open.make_open(Version(4), ASN(65000), HoldTime(180), router_id, Capabilities())
        wire = message.pack_message(Negotiated.UNSET)
        self.assertEqual(wire[Message.HEADER_LEN :], b'\x04\xfd\xe8\x00\xb4\xc0\x00\x02\x01\x00')
        received = Open.unpack_message(wire[Message.HEADER_LEN :], Negotiated.UNSET)
        self.assertEqual(received.router_id, router_id)
        self.assertEqual(received.router_id.top(), '192.0.2.1')

    def test_router_id_from_string_rejects_invalid_ipv4(self) -> None:
        for address in ('256.0.2.1', '192.0.2', 'not-an-address', '2001:db8::1', '::ffff:192.0.2.1'):
            with self.subTest(address=address):
                with self.assertRaises((ValueError, OSError)):
                    RouterID.from_string(address)


if __name__ == '__main__':
    unittest.main()
