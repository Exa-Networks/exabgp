#!/usr/bin/env python3
# encoding: utf-8

"""EVPN NLRI must stay parseable when a member renders empty"""

import json


class TestEvpnEmptyMembersStayJson:
    """An EVPN member which renders empty left a trailing or doubled comma"""

    @staticmethod
    def _decoded(klass, data):
        return klass.unpack(data)

    def test_ethernet_ad_without_a_label_parses(self) -> None:
        from exabgp.bgp.message.update.nlri.evpn.ethernetad import EthernetAD
        from exabgp.bgp.message.update.nlri.qualifier.labels import Labels

        nlri = EthernetAD.unpack(b'\x00' * 8 + b'\x00' * 10 + b'\x00' * 4 + b'\x00' * 3)
        nlri.label = Labels.NOLABEL
        json.loads(nlri.json())

    def test_ethernet_ad_without_a_route_distinguisher_parses(self) -> None:
        from exabgp.bgp.message.update.nlri.evpn.ethernetad import EthernetAD
        from exabgp.bgp.message.update.nlri.qualifier.rd import RouteDistinguisher

        nlri = EthernetAD.unpack(b'\x00' * 8 + b'\x00' * 10 + b'\x00' * 4 + b'\x00' * 3)
        nlri.rd = RouteDistinguisher.NORD
        json.loads(nlri.json())

    def test_multicast_without_a_route_distinguisher_parses(self) -> None:
        from exabgp.bgp.message.update.nlri.evpn.multicast import Multicast
        from exabgp.bgp.message.update.nlri.qualifier.rd import RouteDistinguisher

        nlri = Multicast.unpack(b'\x00' * 8 + b'\x00' * 4 + b'\x20' + b'\x00' * 4)
        nlri.rd = RouteDistinguisher.NORD
        json.loads(nlri.json())
