#!/usr/bin/env python
# encoding: utf-8
"""
open.py

Created by Thomas Morin, Orange on 2015-07-10.
Copyright (c) 2009-2015 Orange. All rights reserved.
"""

import unittest

from exabgp.reactor.protocol import AFI, SAFI

from exabgp.bgp.message.update import Attributes

from exabgp.bgp.message.update.attribute.localpref import LocalPreference
from exabgp.bgp.message.update.attribute.community.extended.communities \
    import ExtendedCommunities
from exabgp.bgp.message.update.attribute.community.extended \
    import RouteTargetASN2Number as RouteTarget
from exabgp.bgp.message.update.attribute.community.extended.encapsulation \
    import Encapsulation

from exabgp.bgp.message.update.nlri.ipvpn import IPVPN

from exabgp.bgp.message.update.nlri.rtc import RTC

from exabgp.bgp.message.update.nlri.evpn.mac import MAC as EVPNMAC
from exabgp.bgp.message.update.nlri.evpn.multicast import Multicast as EVPNMulticast
from exabgp.bgp.message.update.nlri.evpn.prefix import Prefix as EVPNPrefix
from exabgp.bgp.message.update.nlri.evpn.nlri import EVPN

from exabgp.bgp.message.update.nlri.qualifier.rd import RouteDistinguisher
from exabgp.bgp.message.update.nlri.qualifier.labels import Labels
from exabgp.bgp.message.update.nlri.qualifier.esi import ESI
from exabgp.bgp.message.update.nlri.qualifier.etag import EthernetTag
from exabgp.bgp.message.update.nlri.qualifier.mac import MAC

from exabgp.protocol.ip import IP

from exabgp.bgp.message import OUT

from exabgp.configuration.setup import environment
environment.setup('')


class TestNLRIs(unittest.TestCase):

    # Tests on IPVPN NLRIs

    def test200_IPVPNCreatePackUnpack(self):
        '''Test pack/unpack for IPVPN routes'''
        nlri = IPVPN.new(AFI(AFI.ipv4), SAFI(SAFI.mpls_vpn),
                         IP.pton("1.2.3.0"), 24,
                         Labels([42], True), 
                         RouteDistinguisher.fromElements("42.42.42.42", 5))

        packed = nlri.pack()
        unpacked,leftover = IPVPN.unpack_nlri(AFI(AFI.ipv4), SAFI(SAFI.mpls_vpn),
                                              packed, OUT.UNSET, None)

        self.assertEqual(0, len(leftover))

        # TODO: compare packed with a reference encoding verified 
        # as conformant with RFC4364

        self.assertTrue(isinstance(unpacked, IPVPN))

        self.assertEqual("1.2.3.0/24", unpacked.cidr.prefix())
        self.assertEqual(1, len(unpacked.labels.labels))
        self.assertEqual(42, unpacked.labels.labels[0])
        self.assertEqual("42.42.42.42:5", unpacked.rd._str())

    # Tests on EVPN NLRIs

    def test99_EVPNMACCreatePackUnpack(self):
        '''Test pack/unpack for E-VPN MAC routes'''
        nlri = EVPNMAC(RouteDistinguisher.fromElements("42.42.42.42", 5),
                       ESI(),
                       EthernetTag(111),
                       MAC("01:02:03:04:05:06"), 6*8,
                       Labels([42], True),
                       IP.create("1.1.1.1"))

        packed = nlri.pack()

        unpacked,leftover = EVPN.unpack_nlri(AFI(AFI.l2vpn), SAFI(SAFI.evpn),
                                             packed, OUT.UNSET, None)

        self.assertEqual(0, len(leftover))

        # TODO: compare packed with a reference encoding verified 
        # as conformant with RFC7432

        self.assertTrue(isinstance(unpacked, EVPNMAC))

        self.assertEqual("42.42.42.42:5", unpacked.rd._str())
        self.assertEqual(ESI.DEFAULT, unpacked.esi.esi)
        self.assertEqual(EthernetTag(111), unpacked.etag)
        self.assertEqual(MAC("01:02:03:04:05:06"), unpacked.mac)

        self.assertEqual(IP.create("1.1.1.1"), unpacked.ip)

        self.assertEqual(1, len(unpacked.label.labels))
        self.assertEqual(42, unpacked.label.labels[0])

    def test99_EVPNMulticastCreatePackUnpack(self):
        '''Test pack/unpack for E-VPN Multicast routes'''

        nlri = EVPNMulticast(RouteDistinguisher.fromElements("42.42.42.42", 5),
                             EthernetTag(111),
                             IP.create("1.1.1.1"))

        packed = nlri.pack()

        unpacked,leftover = EVPN.unpack_nlri(AFI(AFI.l2vpn), SAFI(SAFI.evpn),
                                             packed, OUT.UNSET, None)

        self.assertEqual(0, len(leftover))

        # TODO: compare packed with a reference encoding verified 
        # as conformant with RFC7432

        self.assertTrue(isinstance(unpacked, EVPNMulticast))

        self.assertEqual("42.42.42.42:5", unpacked.rd._str())
        self.assertEqual(EthernetTag(111), unpacked.etag)
        self.assertEqual(IP.create("1.1.1.1"), unpacked.ip)

    def test99_EVPNPrefixCreatePackUnpack(self):
        '''Test pack/unpack for E-VPN Prefix routes'''

        nlri = EVPNPrefix(RouteDistinguisher.fromElements("42.42.42.42", 5),
                          ESI(),
                          EthernetTag(111),
                          Labels([42], True),
                          IP.create("1.1.1.0"),24,
                          IP.create("2.2.2.2"),
                          )

        packed = nlri.pack()

        unpacked,leftover = EVPN.unpack_nlri(AFI(AFI.l2vpn), SAFI(SAFI.evpn),
                                             packed, OUT.UNSET, None)

        self.assertEqual(0, len(leftover))

        # TODO: compare packed with a reference encoding verified 
        # as conformant with RFC7432

        self.assertTrue(isinstance(unpacked, EVPNPrefix))

        self.assertEqual("42.42.42.42:5", unpacked.rd._str())
        self.assertEqual(ESI.DEFAULT, unpacked.esi.esi)
        self.assertEqual(EthernetTag(111), unpacked.etag)
        self.assertEqual(IP.create("1.1.1.0"), unpacked.ip)
        self.assertEqual(24, unpacked.iplen)
        self.assertEqual(IP.create("2.2.2.2"), unpacked.gwip)
        self.assertEqual(1, len(unpacked.label.labels))
        self.assertEqual(42, unpacked.label.labels[0])

    def test100_EVPNMACHashEqual(self):
        '''
        Two indistinct EVPN NLRI should
        hash to the same value, and be equal
        '''

        nlri1 = EVPNMAC(RouteDistinguisher.fromElements("42.42.42.42", 5),
                        ESI(),
                        EthernetTag(111),
                        MAC("01:02:03:04:05:06"), 6*8,
                        Labels([42], True),
                        IP.create("1.1.1.1"))

        nlri2 = EVPNMAC(RouteDistinguisher.fromElements("42.42.42.42", 5),
                        ESI(),
                        EthernetTag(111),
                        MAC("01:02:03:04:05:06"), 6*8,
                        Labels([42], True),
                        IP.create("1.1.1.1"))

        self.assertEqual(hash(nlri1), hash(nlri2))
        self.assertEqual(nlri1, nlri2)

    def test101_EVPNHashEqual_somefieldsvary(self):
        '''
        Two EVPN MAC NLRIs differing by their ESI or label or RD,
        or nexthop, but otherwise identical should hash to the same value,
        and be equal
        '''

        nlri0 = EVPNMAC(RouteDistinguisher.fromElements("42.42.42.42", 5),
                        ESI(),
                        EthernetTag(111),
                        MAC("01:02:03:04:05:06"), 6*8,
                        Labels([42], True),
                        IP.create("1.1.1.1"))

        # Esi
        nlri1 = EVPNMAC(RouteDistinguisher.fromElements("42.42.42.42", 5),
                        ESI(['1' for _ in range(0,10)]),
                        EthernetTag(111),
                        MAC("01:02:03:04:05:06"), 6*8,
                        Labels([42], True),
                        IP.create("1.1.1.1"))

        # label
        nlri2 = EVPNMAC(RouteDistinguisher.fromElements("42.42.42.42", 5),
                        ESI(),
                        EthernetTag(111),
                        MAC("01:02:03:04:05:06"), 6*8,
                        Labels([4444], True),
                        IP.create("1.1.1.1"))

        # IP: different IPs, but same MACs: different route
        nlri3 = EVPNMAC(RouteDistinguisher.fromElements("42.42.42.42", 5),
                        ESI(),
                        EthernetTag(111),
                        MAC("01:02:03:04:05:06"), 6*8,
                        Labels([42], True),
                        IP.create("2.2.2.2"))

        # with a next hop...
        nlri4 = EVPNMAC(RouteDistinguisher.fromElements("42.42.42.42", 5),
                        ESI(),
                        EthernetTag(111),
                        MAC("01:02:03:04:05:06"), 6*8,
                        Labels([42], True),
                        IP.create("1.1.1.1"),
                        IP.pton("10.10.10.10"))
        nlri5 = EVPNMAC(RouteDistinguisher.fromElements("42.42.42.42", 5),
                        ESI(),
                        EthernetTag(111),
                        MAC("01:02:03:04:05:06"), 6*8,
                        Labels([42], True),
                        IP.create("1.1.1.1"),
                        IP.pton("11.11.11.11"))

        self.assertEqual(hash(nlri0), hash(nlri1))
        self.assertEqual(hash(nlri0), hash(nlri2))
        self.assertEqual(hash(nlri0), hash(nlri4))
        self.assertEqual(nlri0, nlri1)
        self.assertEqual(nlri0, nlri2)
        self.assertEqual(nlri0, nlri4)
        self.assertEqual(nlri1, nlri2)
        self.assertEqual(nlri1, nlri4)
        self.assertEqual(nlri2, nlri4)
        self.assertEqual(nlri4, nlri5)

        self.assertNotEqual(hash(nlri0), hash(nlri3))
        self.assertNotEqual(nlri0, nlri3)
        self.assertNotEqual(nlri1, nlri3)
        self.assertNotEqual(nlri2, nlri3)
        self.assertNotEqual(nlri3, nlri4)

    # tests on RTC NLRI

    def test99_RTCCreatePackUnpack(self):
        '''Test pack/unpack for RTC routes'''

        nlri = RTC.new(AFI(AFI.ipv4), SAFI(SAFI.rtc),
                       64512,
                       RouteTarget(64577,123))

        packed = nlri.pack()
        unpacked,leftover = RTC.unpack_nlri(AFI(AFI.ipv4), SAFI(SAFI.mpls_vpn),
                                            packed, OUT.UNSET, None)

        self.assertEqual(0, len(leftover))

        # TODO: compare packed with a reference encoding verified 
        # as conformant with RFC4684

        self.assertTrue(isinstance(unpacked, RTC))

        self.assertEqual(64512, unpacked.origin)

        self.assertTrue(isinstance(unpacked.rt, RouteTarget))
        self.assertEqual(64577, unpacked.rt.asn)
        self.assertEqual(123, unpacked.rt.number)

    def test98_RTCWildcardPackUnpack(self):
        '''Test pack/unpack for RTC routes'''

        nlri = RTC.new(AFI(AFI.ipv4), SAFI(SAFI.rtc),
                       0, None)

        packed = nlri.pack()
        unpacked,leftover = RTC.unpack_nlri(AFI(AFI.ipv4), SAFI(SAFI.mpls_vpn),
                                            packed, OUT.UNSET, None)

        self.assertEqual(0, len(leftover))

        # TODO: compare packed with a reference encoding verified 
        # as conformant with RFC4684

        self.assertTrue(isinstance(unpacked, RTC))

        self.assertEqual(0, unpacked.origin)

        self.assertIsNone(unpacked.rt)


    # tests on attributes

    def test4_DistinctAttributes(self):
        atts1 = Attributes()
        atts1.add(LocalPreference(10))

        atts2 = Attributes()
        atts2.add(LocalPreference(20))

        self.assertNotEqual(atts1, atts2)

    def test5_SameAttributes(self):
        atts1 = Attributes()
        atts1.add(LocalPreference(10))

        atts2 = Attributes()
        atts2.add(LocalPreference(10))

        self.assertEqual(hash(atts1), hash(atts2))
        self.assertEqual(atts1, atts2)

    def test6_SameAttributesOrderMultivalued(self):
        atts1 = Attributes()
        eComs1 = ExtendedCommunities()
        eComs1.communities.append(RouteTarget(64512, 1))
        eComs1.communities.append(Encapsulation(Encapsulation.Type.VXLAN))
        eComs1.communities.append(RouteTarget(64512, 2))
        atts1.add(eComs1)

        atts2 = Attributes()
        eComs2 = ExtendedCommunities()
        eComs2.communities.append(RouteTarget(64512, 2))
        eComs2.communities.append(RouteTarget(64512, 1))
        eComs2.communities.append(Encapsulation(Encapsulation.Type.VXLAN))
        atts2.add(eComs2)

        self.assertEqual(hash(atts1), hash(atts2))
        self.assertEqual(atts1, atts2)

    def test10_Ecoms(self):
        eComs1 = ExtendedCommunities()
        eComs1.communities.append(Encapsulation(Encapsulation.Type.VXLAN))
        atts1 = Attributes()
        atts1.add(eComs1)

        eComs2 = ExtendedCommunities()
        eComs2.communities.append(Encapsulation(Encapsulation.Type.VXLAN))
        eComs2.communities.append(RouteTarget(64512, 1))
        atts2 = Attributes()
        atts2.add(eComs2)

        self.assertFalse(atts1.sameValuesAs(atts2))
        self.assertFalse(atts2.sameValuesAs(atts1))

    def test11_RTs(self):
        rt1a = RouteTarget(64512, 1)
        rt1b = RouteTarget(64512, 1)
        rt3 = RouteTarget(64512, 2)
        rt4 = RouteTarget(64513, 1)

        self.assertEqual(hash(rt1a), hash(rt1b))
        self.assertNotEqual(hash(rt1a), hash(rt3))
        self.assertNotEqual(hash(rt1a), hash(rt4))

        self.assertEqual(rt1a, rt1b)
        self.assertNotEqual(rt1a, rt3)
        self.assertNotEqual(rt1a, rt4)

        self.assertEqual(set([rt1a]), set([rt1b]))
        self.assertEqual(1, len(set([rt1a]).intersection(set([rt1b]))))


if __name__ == '__main__':
    unittest.main()
