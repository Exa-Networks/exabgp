"""announce/mup.py

Created by Thomas Mangin on 2017-07-06.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations


from exabgp.rib.route import Route

from exabgp.protocol.family import AFI
from exabgp.protocol.family import SAFI

from exabgp.configuration.announce import ParseAnnounce
from exabgp.configuration.announce.route_builder import _build_type_selector_route
from exabgp.configuration.core import Parser
from exabgp.configuration.core import Tokeniser
from exabgp.configuration.core import Scope
from exabgp.configuration.core import Error
from exabgp.configuration.schema import (
    TypeSelectorBuilder,
    Leaf,
    LeafList,
    ValueType,
    ActionTarget,
    ActionOperation,
    ActionKey,
)
from exabgp.configuration.validator import LegacyParserValidator

from exabgp.configuration.static.parser import next_hop
from exabgp.configuration.static.mpls import prefix_sid_srv6
from exabgp.configuration.static.mpls import srv6_mup_isd
from exabgp.configuration.static.mpls import srv6_mup_dsd
from exabgp.configuration.static.mpls import srv6_mup_t1st
from exabgp.configuration.static.mpls import srv6_mup_t2st
from exabgp.configuration.static.parser import extended_community


class AnnounceMup(ParseAnnounce):
    # Schema for MUP routes using TypeSelectorBuilder
    # First token selects type (mup-isd, mup-dsd, etc.), factory parses NLRI fields
    # Note: MUP factories create complete NLRIs - no post-factory NLRI mutation needed
    schema = TypeSelectorBuilder(
        description='MUP route announcement',
        type_factories={
            'mup-isd': srv6_mup_isd,
            'mup-dsd': srv6_mup_dsd,
            'mup-t1st': srv6_mup_t1st,
            'mup-t2st': srv6_mup_t2st,
        },
        factory_needs_action=False,  # MUP factories: factory(tokeniser, afi)
        children={
            'next-hop': Leaf(
                type=ValueType.NEXT_HOP,
                description='Next hop IP address',
                target=ActionTarget.NEXTHOP_ATTRIBUTE,
                operation=ActionOperation.SET,
                key=ActionKey.COMMAND,
                validator=LegacyParserValidator(parser_func=next_hop, name='next-hop', accepts_afi=True),
            ),
            'bgp-prefix-sid-srv6': Leaf(
                type=ValueType.STRING,
                description='SRv6 BGP Prefix SID',
                target=ActionTarget.ATTRIBUTE,
                operation=ActionOperation.ADD,
                key=ActionKey.NAME,
                validator=LegacyParserValidator(parser_func=prefix_sid_srv6, name='bgp-prefix-sid-srv6'),
            ),
            'extended-community': LeafList(
                type=ValueType.EXTENDED_COMMUNITY,
                description='Extended communities',
                target=ActionTarget.ATTRIBUTE,
                operation=ActionOperation.ADD,
                key=ActionKey.NAME,
                validator=LegacyParserValidator(parser_func=extended_community, name='extended-community'),
            ),
        },
    )

    # Type-specific NLRI syntaxes (not modeled in schema children)
    _type_definitions = [
        'mup-isd <ip prefix> rd <rd>',
        'mup-dsd <ip address> rd <rd>',
        'mup-t1st <ip prefix> rd <rd> teid <teid> qfi <qfi> endpoint <endpoint> [source <source_addr>]',
        'mup-t2st <endpoint address> rd <rd> teid <teid>',
    ]

    name = 'mup'

    @property
    def syntax(self) -> str:
        """Syntax combining type-specific NLRI syntax with schema-generated attributes."""
        defn = ';\n  '.join(self._type_definitions + self.schema.definition)
        return f'mup {{\n  <safi> {defn};\n}}'

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
    def check(route: Route, afi: AFI | None) -> bool:
        return True


@ParseAnnounce.register_family(AFI.ipv4, SAFI.mup, ActionTarget.SCOPE, ActionOperation.EXTEND, ActionKey.NAME)
def mup_ip_v4(tokeniser: Tokeniser) -> list[Route]:
    return _build_type_selector_route(tokeniser, AnnounceMup.schema, AFI.ipv4, SAFI.mup, AnnounceMup.check)


@ParseAnnounce.register_family(AFI.ipv6, SAFI.mup, ActionTarget.SCOPE, ActionOperation.EXTEND, ActionKey.NAME)
def mup_ip_v6(tokeniser: Tokeniser) -> list[Route]:
    return _build_type_selector_route(tokeniser, AnnounceMup.schema, AFI.ipv6, SAFI.mup, AnnounceMup.check)
