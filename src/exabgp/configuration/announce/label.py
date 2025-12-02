"""announce/label.py

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

from exabgp.bgp.message.update.nlri.label import Label
from exabgp.bgp.message.update.nlri.qualifier import Labels

from exabgp.configuration.announce import ParseAnnounce
from exabgp.configuration.announce.path import AnnouncePath
from exabgp.configuration.announce.ip import _build_route
from exabgp.configuration.core import Parser
from exabgp.configuration.core import Tokeniser
from exabgp.configuration.core import Scope
from exabgp.configuration.core import Error
from exabgp.configuration.schema import RouteBuilder, Leaf, ValueType
from exabgp.configuration.validator import LegacyParserValidator

from exabgp.configuration.static.parser import prefix
from exabgp.configuration.static.mpls import label


class AnnounceLabel(AnnouncePath):
    # Schema extends AnnouncePath with label using RouteBuilder
    schema = RouteBuilder(
        description='MPLS labeled route announcement',
        nlri_factory=Label,
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
    # put next-hop first as it is a requirement atm
    definition = [
        'label <15 bits number>',
    ] + AnnouncePath.definition

    syntax = '<safi> <ip>/<netmask> { \n   ' + ' ;\n   '.join(definition) + '\n}'

    known = {**AnnouncePath.known, 'label': label}
    action = {**AnnouncePath.action, 'label': 'nlri-set'}
    assign = {**AnnouncePath.assign, 'label': 'labels'}

    name = 'vpn'
    afi: AFI | None = None

    def __init__(self, parser: Parser, scope: Scope, error: Error) -> None:
        AnnouncePath.__init__(self, parser, scope, error)

    def clear(self) -> None:
        pass

    @staticmethod
    def check(change: Change, afi: AFI | None) -> bool:
        if not AnnouncePath.check(change, afi):
            return False

        # has_label() confirms the NLRI type has a labels attribute
        if change.nlri.action == Action.ANNOUNCE and change.nlri.has_label():
            if cast(Label, change.nlri).labels is Labels.NOLABEL:
                return False

        return True


@ParseAnnounce.register('nlri-mpls', 'extend-name', 'ipv4')
def nlri_mpls_v4(tokeniser: Tokeniser) -> list[Change]:
    return _build_route(tokeniser, AnnounceLabel.schema, AFI.ipv4, SAFI.nlri_mpls, AnnounceLabel.check)


@ParseAnnounce.register('nlri-mpls', 'extend-name', 'ipv6')
def nlri_mpls_v6(tokeniser: Tokeniser) -> list[Change]:
    return _build_route(tokeniser, AnnounceLabel.schema, AFI.ipv6, SAFI.nlri_mpls, AnnounceLabel.check)
