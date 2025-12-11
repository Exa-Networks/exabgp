"""announce/label.py

Created by Thomas Mangin on 2017-07-05.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from typing import cast

from exabgp.rib.route import Route

from exabgp.bgp.message import Action

from exabgp.protocol.family import AFI
from exabgp.protocol.family import SAFI

from exabgp.bgp.message.update.nlri.label import Label
from exabgp.bgp.message.update.nlri.qualifier import Labels
from exabgp.bgp.message.update.nlri.settings import INETSettings

from exabgp.configuration.announce import ParseAnnounce
from exabgp.configuration.announce.path import AnnouncePath
from exabgp.configuration.announce.route_builder import _build_route
from exabgp.configuration.core import Parser
from exabgp.configuration.core import Tokeniser
from exabgp.configuration.core import Scope
from exabgp.configuration.core import Error
from exabgp.configuration.schema import RouteBuilder, Leaf, ValueType, ActionTarget, ActionOperation, ActionKey
from exabgp.configuration.validator import LegacyParserValidator

from exabgp.configuration.static.parser import prefix
from exabgp.configuration.static.mpls import label


class AnnounceLabel(AnnouncePath):
    # Schema extends AnnouncePath with label using RouteBuilder (Settings mode)
    schema = RouteBuilder(
        description='MPLS labeled route announcement',
        nlri_class=Label,
        settings_class=INETSettings,
        prefix_parser=prefix,
        assign={
            **AnnouncePath.schema.assign,
            'label': 'labels',
        },
        children={
            **AnnouncePath.schema.children,
            'label': Leaf(
                type=ValueType.LABEL,
                description='MPLS label stack',
                action='nlri-set',
                validator=LegacyParserValidator(parser_func=label, name='label'),
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
        AnnouncePath.__init__(self, parser, scope, error)

    def clear(self) -> None:
        pass

    @staticmethod
    def check(route: Route, afi: AFI | None) -> bool:
        if not AnnouncePath.check(route, afi):
            return False

        # has_label() confirms the NLRI type has a labels attribute
        if route.action == Action.ANNOUNCE and route.nlri.has_label():
            if cast(Label, route.nlri).labels is Labels.NOLABEL:
                return False

        return True


@ParseAnnounce.register_family(AFI.ipv4, SAFI.nlri_mpls, ActionTarget.SCOPE, ActionOperation.EXTEND, ActionKey.NAME)
def nlri_mpls_v4(tokeniser: Tokeniser) -> list[Route]:
    return _build_route(tokeniser, AnnounceLabel.schema, AFI.ipv4, SAFI.nlri_mpls, AnnounceLabel.check)


@ParseAnnounce.register_family(AFI.ipv6, SAFI.nlri_mpls, ActionTarget.SCOPE, ActionOperation.EXTEND, ActionKey.NAME)
def nlri_mpls_v6(tokeniser: Tokeniser) -> list[Route]:
    return _build_route(tokeniser, AnnounceLabel.schema, AFI.ipv6, SAFI.nlri_mpls, AnnounceLabel.check)
