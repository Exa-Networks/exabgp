"""announce/vpls.py

Created by Thomas Mangin on 2017-07-09.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations


from exabgp.rib.change import Change

from exabgp.protocol.family import AFI
from exabgp.protocol.family import SAFI

from exabgp.bgp.message.update.nlri import VPLS

from exabgp.configuration.announce import ParseAnnounce
from exabgp.configuration.announce.route_builder import _build_route
from exabgp.configuration.core import Parser
from exabgp.configuration.core import Tokeniser
from exabgp.configuration.core import Scope
from exabgp.configuration.core import Error
from exabgp.configuration.schema import RouteBuilder, Leaf, LeafList, ValueType
from exabgp.configuration.validator import LegacyParserValidator

from exabgp.configuration.static.parser import attribute
from exabgp.configuration.static.parser import origin
from exabgp.configuration.static.parser import med
from exabgp.configuration.static.parser import as_path
from exabgp.configuration.static.parser import local_preference
from exabgp.configuration.static.parser import atomic_aggregate
from exabgp.configuration.static.parser import aggregator
from exabgp.configuration.static.parser import originator_id
from exabgp.configuration.static.parser import cluster_list
from exabgp.configuration.static.parser import community
from exabgp.configuration.static.parser import extended_community
from exabgp.configuration.static.parser import name as named
from exabgp.configuration.static.parser import split
from exabgp.configuration.static.parser import watchdog
from exabgp.configuration.static.parser import withdraw

from exabgp.configuration.static.mpls import route_distinguisher

from exabgp.configuration.l2vpn.parser import vpls_endpoint
from exabgp.configuration.l2vpn.parser import vpls_size
from exabgp.configuration.l2vpn.parser import vpls_offset
from exabgp.configuration.l2vpn.parser import vpls_base
from exabgp.configuration.l2vpn.parser import next_hop


def _vpls_factory() -> VPLS:
    """Factory function for VPLS NLRI with empty fields."""
    return VPLS(None, None, None, None, None)  # type: ignore[arg-type]


class AnnounceVPLS(ParseAnnounce):
    # Schema for VPLS routes using RouteBuilder (no prefix)
    schema = RouteBuilder(
        description='VPLS route announcement',
        nlri_factory=_vpls_factory,
        prefix_parser=None,  # VPLS has no prefix
        assign={
            'next-hop': 'nexthop',
            'rd': 'rd',
            'endpoint': 'endpoint',
            'offset': 'offset',
            'size': 'size',
            'base': 'base',
        },
        children={
            # NLRI fields
            'next-hop': Leaf(
                type=ValueType.NEXT_HOP,
                description='Next-hop IP address or "self"',
                action='nlri-set',
                validator=LegacyParserValidator(parser_func=next_hop, name='next-hop'),
            ),
            'rd': Leaf(
                type=ValueType.RD,
                description='Route distinguisher',
                action='nlri-set',
                validator=LegacyParserValidator(parser_func=route_distinguisher, name='rd'),
            ),
            'endpoint': Leaf(
                type=ValueType.INTEGER,
                description='VPLS endpoint ID',
                action='nlri-set',
                validator=LegacyParserValidator(parser_func=vpls_endpoint, name='endpoint'),
            ),
            'offset': Leaf(
                type=ValueType.INTEGER,
                description='Block offset',
                action='nlri-set',
                validator=LegacyParserValidator(parser_func=vpls_offset, name='offset'),
            ),
            'size': Leaf(
                type=ValueType.INTEGER,
                description='Block size',
                action='nlri-set',
                validator=LegacyParserValidator(parser_func=vpls_size, name='size'),
            ),
            'base': Leaf(
                type=ValueType.INTEGER,
                description='Label base',
                action='nlri-set',
                validator=LegacyParserValidator(parser_func=vpls_base, name='base'),
            ),
            # Attribute fields
            'origin': Leaf(
                type=ValueType.ORIGIN,
                description='BGP origin attribute',
                action='attribute-add',
                validator=LegacyParserValidator(parser_func=origin, name='origin'),
            ),
            'med': Leaf(
                type=ValueType.MED,
                description='Multi-exit discriminator',
                action='attribute-add',
                validator=LegacyParserValidator(parser_func=med, name='med'),
            ),
            'as-path': LeafList(
                type=ValueType.AS_PATH,
                description='AS path',
                action='attribute-add',
                validator=LegacyParserValidator(parser_func=as_path, name='as-path'),
            ),
            'local-preference': Leaf(
                type=ValueType.LOCAL_PREF,
                description='Local preference',
                action='attribute-add',
                validator=LegacyParserValidator(parser_func=local_preference, name='local-preference'),
            ),
            'atomic-aggregate': Leaf(
                type=ValueType.ATOMIC_AGGREGATE,
                description='Atomic aggregate flag',
                action='attribute-add',
                validator=LegacyParserValidator(parser_func=atomic_aggregate, name='atomic-aggregate'),
            ),
            'aggregator': Leaf(
                type=ValueType.AGGREGATOR,
                description='Aggregator',
                action='attribute-add',
                validator=LegacyParserValidator(parser_func=aggregator, name='aggregator'),
            ),
            'originator-id': Leaf(
                type=ValueType.IP_ADDRESS,
                description='Originator ID',
                action='attribute-add',
                validator=LegacyParserValidator(parser_func=originator_id, name='originator-id'),
            ),
            'cluster-list': LeafList(
                type=ValueType.IP_ADDRESS,
                description='Cluster list',
                action='attribute-add',
                validator=LegacyParserValidator(parser_func=cluster_list, name='cluster-list'),
            ),
            'community': LeafList(
                type=ValueType.COMMUNITY,
                description='Standard BGP communities',
                action='attribute-add',
                validator=LegacyParserValidator(parser_func=community, name='community'),
            ),
            'extended-community': LeafList(
                type=ValueType.EXTENDED_COMMUNITY,
                description='Extended BGP communities',
                action='attribute-add',
                validator=LegacyParserValidator(parser_func=extended_community, name='extended-community'),
            ),
            'attribute': Leaf(
                type=ValueType.HEX_STRING,
                description='Generic BGP attribute',
                action='attribute-add',
                validator=LegacyParserValidator(parser_func=attribute, name='attribute'),
            ),
            'name': Leaf(
                type=ValueType.STRING,
                description='Route name',
                action='attribute-add',
                validator=LegacyParserValidator(parser_func=named, name='name'),
            ),
            'split': Leaf(
                type=ValueType.INTEGER,
                description='Split prefix',
                action='attribute-add',
                validator=LegacyParserValidator(parser_func=split, name='split'),
            ),
            'watchdog': Leaf(
                type=ValueType.STRING,
                description='Watchdog name',
                action='attribute-add',
                validator=LegacyParserValidator(parser_func=watchdog, name='watchdog'),
            ),
            'withdraw': Leaf(
                type=ValueType.BOOLEAN,
                description='Mark for withdrawal',
                action='attribute-add',
                validator=LegacyParserValidator(parser_func=withdraw, name='withdraw'),
            ),
        },
    )

    name = 'vpls'
    afi: AFI | None = None

    @property
    def syntax(self) -> str:
        """Syntax generated from schema (VPLS format without prefix)."""
        defn = '  '.join(self.schema.definition)
        return f'vpls {defn}\n'

    def __init__(self, parser: Parser, scope: Scope, error: Error) -> None:
        ParseAnnounce.__init__(self, parser, scope, error)

    def clear(self) -> None:
        pass

    def post(self) -> bool:
        return self._check()

    @staticmethod
    def check(change: Change, afi: AFI | None) -> bool:
        # No check performed :-(
        return True


@ParseAnnounce.register('vpls', 'extend-name', 'l2vpn')
def vpls_v4(tokeniser: Tokeniser) -> list[Change]:
    return _build_route(tokeniser, AnnounceVPLS.schema, AFI.l2vpn, SAFI.vpls, AnnounceVPLS.check)
