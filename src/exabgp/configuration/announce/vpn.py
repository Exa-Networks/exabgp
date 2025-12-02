"""announce/vpn.py

Created by Thomas Mangin on 2017-07-05.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from typing import cast

from exabgp.rib.change import Change

from exabgp.bgp.message import Action

from exabgp.protocol.family import AFI
from exabgp.protocol.family import SAFI

from exabgp.bgp.message.update.nlri import IPVPN
from exabgp.bgp.message.update.nlri.qualifier import RouteDistinguisher

from exabgp.configuration.announce import ParseAnnounce
from exabgp.configuration.announce.label import AnnounceLabel
from exabgp.configuration.announce.route_builder import _build_route
from exabgp.configuration.core import Parser
from exabgp.configuration.core import Tokeniser
from exabgp.configuration.core import Scope
from exabgp.configuration.core import Error
from exabgp.configuration.schema import RouteBuilder, Leaf, ValueType
from exabgp.configuration.validator import LegacyParserValidator

from exabgp.configuration.static.parser import prefix
from exabgp.configuration.static.mpls import route_distinguisher


class AnnounceVPN(ParseAnnounce):
    # Schema extends AnnounceLabel with route-distinguisher using RouteBuilder
    schema = RouteBuilder(
        description='VPN route announcement',
        nlri_factory=IPVPN,
        prefix_parser=prefix,
        assign={
            **AnnounceLabel.schema.assign,
            'rd': 'rd',
        },
        children={
            **AnnounceLabel.schema.children,
            'rd': Leaf(
                type=ValueType.RD,
                description='Route distinguisher',
                action='nlri-set',
                validator=LegacyParserValidator(parser_func=route_distinguisher, name='rd'),
            ),
        },
    )
    # put next-hop first as it is a requirement atm
    definition = [
        '  (optional) rd 255.255.255.255:65535|65535:65536|65536:65535;\n',
    ] + AnnounceLabel.definition

    syntax = '<safi> <ip>/<netmask> { \n   ' + ' ;\n   '.join(definition) + '\n}'

    name = 'vpn'
    afi: AFI | None = None

    def __init__(self, parser: Parser, scope: Scope, error: Error) -> None:
        ParseAnnounce.__init__(self, parser, scope, error)

    def clear(self) -> None:
        pass

    @staticmethod
    def check(change: Change, afi: AFI | None) -> bool:
        if not AnnounceLabel.check(change, afi):
            return False

        # has_rd() confirms the NLRI type has an rd attribute
        if change.nlri.action == Action.ANNOUNCE and change.nlri.has_rd():
            if cast(IPVPN, change.nlri).rd is RouteDistinguisher.NORD:
                return False

        return True


@ParseAnnounce.register('mpls-vpn', 'extend-name', 'ipv4')
def mpls_vpn_v4(tokeniser: Tokeniser) -> list[Change]:
    return _build_route(tokeniser, AnnounceVPN.schema, AFI.ipv4, SAFI.mpls_vpn, AnnounceVPN.check)


@ParseAnnounce.register('mpls-vpn', 'extend-name', 'ipv6')
def mpls_vpn_v6(tokeniser: Tokeniser) -> list[Change]:
    return _build_route(tokeniser, AnnounceVPN.schema, AFI.ipv6, SAFI.mpls_vpn, AnnounceVPN.check)
