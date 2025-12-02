"""announce/mup.py

Created by Thomas Mangin on 2017-07-06.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations


from exabgp.rib.change import Change

from exabgp.protocol.family import AFI
from exabgp.protocol.family import SAFI

from exabgp.configuration.announce import ParseAnnounce
from exabgp.configuration.announce.route_builder import _build_type_selector_route
from exabgp.configuration.core import Parser
from exabgp.configuration.core import Tokeniser
from exabgp.configuration.core import Scope
from exabgp.configuration.core import Error
from exabgp.configuration.schema import TypeSelectorBuilder, Leaf, LeafList, ValueType
from exabgp.configuration.validator import LegacyParserValidator

from exabgp.configuration.static.parser import next_hop
from exabgp.configuration.static.mpls import label
from exabgp.configuration.static.mpls import prefix_sid_srv6
from exabgp.configuration.static.mpls import srv6_mup_isd
from exabgp.configuration.static.mpls import srv6_mup_dsd
from exabgp.configuration.static.mpls import srv6_mup_t1st
from exabgp.configuration.static.mpls import srv6_mup_t2st
from exabgp.configuration.static.parser import extended_community


class AnnounceMup(ParseAnnounce):
    # Schema for MUP routes using TypeSelectorBuilder
    # First token selects type (mup-isd, mup-dsd, etc.), factory parses NLRI fields
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
                action='nexthop-and-attribute',
                validator=LegacyParserValidator(parser_func=next_hop, name='next-hop', accepts_afi=True),
            ),
            'label': Leaf(
                type=ValueType.LABEL,
                description='MPLS label',
                action='nlri-set',
                validator=LegacyParserValidator(parser_func=label, name='label'),
            ),
            'bgp-prefix-sid-srv6': Leaf(
                type=ValueType.STRING,
                description='SRv6 BGP Prefix SID',
                action='attribute-add',
                validator=LegacyParserValidator(parser_func=prefix_sid_srv6, name='bgp-prefix-sid-srv6'),
            ),
            'extended-community': LeafList(
                type=ValueType.EXTENDED_COMMUNITY,
                description='Extended communities',
                action='attribute-add',
                validator=LegacyParserValidator(parser_func=extended_community, name='extended-community'),
            ),
        },
    )

    definition = [
        'mup-isd <ip prefix> rd <rd>',
        'mup-dsd <ip address> rd <rd>',
        'mup-t1st <ip prefix> rd <rd> teid <teid> qfi <qfi> endpoint <endpoint> [source <source_addr>]',
        'mup-t2st <endpoint address> rd <rd> teid <teid>',
        'next-hop <ip>',
        'extended-community [ mup:<16 bits number>:<ipv4 formated number> target:<16 bits number>:<ipv4 formated number> ]',
        'bgp-prefix-sid-srv6 ( l3-service <ipv6> <behavior> [<LBL>,<LNL>,<FL>,<AL>,<Tpose-Len>,<Tpose-Offset>])',
    ]

    syntax = 'mup {{\n  <safi> {};\n}}'.format(';\n  '.join(definition))

    known = {
        'label': label,
        'bgp-prefix-sid-srv6': prefix_sid_srv6,
        'next-hop': next_hop,
        'extended-community': extended_community,
    }
    action = {
        'label': 'nlri-set',
        'next-hop': 'nexthop-and-attribute',
        'bgp-prefix-sid-srv6': 'attribute-add',
        'extended-community': 'attribute-add',
    }

    assign = {}
    default = {}

    name = 'mup'

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
        return True


@ParseAnnounce.register('mup', 'extend-name', 'ipv4')
def mup_ip_v4(tokeniser: Tokeniser) -> list[Change]:
    return _build_type_selector_route(tokeniser, AnnounceMup.schema, AFI.ipv4, SAFI.mup, AnnounceMup.check)


@ParseAnnounce.register('mup', 'extend-name', 'ipv6')
def mup_ip_v6(tokeniser: Tokeniser) -> list[Change]:
    return _build_type_selector_route(tokeniser, AnnounceMup.schema, AFI.ipv6, SAFI.mup, AnnounceMup.check)
