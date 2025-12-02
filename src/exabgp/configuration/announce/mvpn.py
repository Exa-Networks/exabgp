"""announce/mvpn.py

MVPN (Multicast VPN) route announcement parser.

Created by Thomas Mangin.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations


from exabgp.rib.change import Change

from exabgp.protocol.family import AFI
from exabgp.protocol.family import SAFI

from exabgp.configuration.announce import ParseAnnounce
from exabgp.configuration.announce.ip import AnnounceIP
from exabgp.configuration.announce.route_builder import _build_type_selector_route
from exabgp.configuration.core import Parser
from exabgp.configuration.core import Tokeniser
from exabgp.configuration.core import Scope
from exabgp.configuration.core import Error
from exabgp.configuration.schema import TypeSelectorBuilder

from exabgp.configuration.static.mpls import mvpn_sourcead
from exabgp.configuration.static.mpls import mvpn_sourcejoin
from exabgp.configuration.static.mpls import mvpn_sharedjoin


class AnnounceMVPN(ParseAnnounce):
    # Schema for MVPN routes using TypeSelectorBuilder
    # First token selects type (source-ad, source-join, shared-join), factory parses NLRI fields
    # Inherits attribute children from AnnounceIP.schema
    schema = TypeSelectorBuilder(
        description='MVPN route announcement',
        type_factories={
            'source-ad': mvpn_sourcead,
            'source-join': mvpn_sourcejoin,
            'shared-join': mvpn_sharedjoin,
        },
        factory_needs_action=True,  # MVPN factories: factory(tokeniser, afi, action)
        children={
            **AnnounceIP.schema.children,
        },
    )

    # Type-specific NLRI syntaxes (not modeled in schema children)
    _type_definitions = [
        'source-ad source <ip> group <ip> rd <rd>',
        'shared-join rp <ip> group <ip> rd <rd> source-as <source-as>',
        'source-join source <ip> group <ip> rd <rd> source-as <source-as>',
    ]

    name = 'mvpn'
    afi: AFI | None = None

    @property
    def syntax(self) -> str:
        """Syntax combining type-specific NLRI syntax with schema-generated attributes."""
        defn = ' ;\n   '.join(self._type_definitions + self.schema.definition)
        return f'<safi> {{ \n   {defn}\n}}'

    def __init__(self, parser: Parser, scope: Scope, error: Error) -> None:
        ParseAnnounce.__init__(self, parser, scope, error)

    def clear(self) -> None:
        pass

    def pre(self) -> bool:
        self.scope.to_context(self.name)
        return True

    def post(self) -> bool:
        return ParseAnnounce.post(self) and self._check()

    @staticmethod
    def check(change: Change, afi: AFI | None) -> bool:
        if not AnnounceIP.check(change, afi):
            return False

        return True


@ParseAnnounce.register('mcast-vpn', 'extend-name', 'ipv4')
def mcast_vpn_v4(tokeniser: Tokeniser) -> list[Change]:
    return _build_type_selector_route(tokeniser, AnnounceMVPN.schema, AFI.ipv4, SAFI.mcast_vpn, AnnounceMVPN.check)


@ParseAnnounce.register('mcast-vpn', 'extend-name', 'ipv6')
def mcast_vpn_v6(tokeniser: Tokeniser) -> list[Change]:
    return _build_type_selector_route(tokeniser, AnnounceMVPN.schema, AFI.ipv6, SAFI.mcast_vpn, AnnounceMVPN.check)
