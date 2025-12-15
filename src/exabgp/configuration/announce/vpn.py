"""announce/vpn.py

Created by Thomas Mangin on 2017-07-05.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from typing import cast

from exabgp.rib.route import Route


from exabgp.protocol.family import AFI
from exabgp.protocol.family import SAFI

from exabgp.bgp.message.update.nlri import IPVPN
from exabgp.bgp.message.update.nlri.qualifier import RouteDistinguisher
from exabgp.bgp.message.update.nlri.settings import INETSettings

from exabgp.configuration.announce import ParseAnnounce
from exabgp.configuration.announce.label import AnnounceLabel
from exabgp.configuration.announce.route_builder import _build_route
from exabgp.configuration.core import Parser
from exabgp.configuration.core import Tokeniser
from exabgp.configuration.core import Scope
from exabgp.configuration.core import Error
from exabgp.configuration.schema import RouteBuilder, Leaf, ValueType, ActionTarget, ActionOperation, ActionKey
from exabgp.configuration.validator import LegacyParserValidator

from exabgp.configuration.static.parser import prefix
from exabgp.configuration.static.mpls import route_distinguisher


class AnnounceVPN(ParseAnnounce):
    # Schema extends AnnounceLabel with route-distinguisher using RouteBuilder (Settings mode)
    schema = RouteBuilder(
        description='VPN route announcement',
        nlri_class=IPVPN,
        settings_class=INETSettings,
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
                target=ActionTarget.NLRI,
                operation=ActionOperation.SET,
                key=ActionKey.FIELD,
                validator=LegacyParserValidator(parser_func=route_distinguisher, name='rd'),
            ),
        },
    )

    name = 'vpn'
    afi: AFI | None = None

    @property
    def syntax(self) -> str:
        """Syntax generated from schema."""
        return self.schema.syntax

    def __init__(self, parser: Parser, scope: Scope, error: Error) -> None:
        ParseAnnounce.__init__(self, parser, scope, error)

    def clear(self) -> None:
        pass

    @staticmethod
    def check(route: Route, afi: AFI | None) -> bool:
        if not AnnounceLabel.check(route, afi):
            return False

        # has_rd() confirms the NLRI type has an rd attribute
        # RD is required for announces
        if route.nlri.has_rd():
            if cast(IPVPN, route.nlri).rd is RouteDistinguisher.NORD:
                return False

        return True


@ParseAnnounce.register_family(AFI.ipv4, SAFI.mpls_vpn, ActionTarget.SCOPE, ActionOperation.EXTEND, ActionKey.NAME)
def mpls_vpn_v4(tokeniser: Tokeniser) -> list[Route]:
    return _build_route(tokeniser, AnnounceVPN.schema, AFI.ipv4, SAFI.mpls_vpn, AnnounceVPN.check)


@ParseAnnounce.register_family(AFI.ipv6, SAFI.mpls_vpn, ActionTarget.SCOPE, ActionOperation.EXTEND, ActionKey.NAME)
def mpls_vpn_v6(tokeniser: Tokeniser) -> list[Route]:
    return _build_route(tokeniser, AnnounceVPN.schema, AFI.ipv6, SAFI.mpls_vpn, AnnounceVPN.check)
