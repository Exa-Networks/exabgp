"""announce/ip.py

Created by Thomas Mangin on 2015-06-04.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations


from exabgp.protocol.ip import IP

from exabgp.rib.route import Route

from exabgp.bgp.message import Action

from exabgp.protocol.family import AFI
from exabgp.protocol.family import SAFI

from exabgp.bgp.message.update.nlri.inet import INET

from exabgp.configuration.announce import ParseAnnounce
from exabgp.configuration.core import Parser
from exabgp.configuration.core import Tokeniser
from exabgp.configuration.core import Scope
from exabgp.configuration.core import Error
from exabgp.configuration.schema import RouteBuilder, Leaf, LeafList, ValueType

from exabgp.configuration.static.parser import prefix

# Import and re-export _build_route for backward compatibility
from exabgp.configuration.announce.route_builder import _build_route  # noqa: F401


class AnnounceIP(ParseAnnounce):
    # Schema definition for IP route announcements using RouteBuilder
    # RouteBuilder handles the token loop that was previously in ip() function
    schema = RouteBuilder(
        description='IP route announcement',
        nlri_factory=INET,
        prefix_parser=prefix,
        children={
            'next-hop': Leaf(
                type=ValueType.NEXT_HOP,
                description='Next-hop IP address or "self"',
                action='nexthop-and-attribute',
            ),
            'origin': Leaf(
                type=ValueType.ORIGIN,
                description='BGP origin attribute',
                choices=['igp', 'egp', 'incomplete'],
                action='attribute-add',
            ),
            'med': Leaf(
                type=ValueType.MED,
                description='Multi-exit discriminator',
                action='attribute-add',
            ),
            'as-path': LeafList(
                type=ValueType.AS_PATH,
                description='AS path',
                action='attribute-add',
            ),
            'local-preference': Leaf(
                type=ValueType.LOCAL_PREF,
                description='Local preference',
                action='attribute-add',
            ),
            'atomic-aggregate': Leaf(
                type=ValueType.ATOMIC_AGGREGATE,
                description='Atomic aggregate flag',
                action='attribute-add',
            ),
            'aggregator': Leaf(
                type=ValueType.AGGREGATOR,
                description='Aggregator (AS number and IP)',
                action='attribute-add',
            ),
            'originator-id': Leaf(
                type=ValueType.IP_ADDRESS,
                description='Originator ID',
                action='attribute-add',
            ),
            'cluster-list': LeafList(
                type=ValueType.IP_ADDRESS,
                description='Cluster list',
                action='attribute-add',
            ),
            'community': LeafList(
                type=ValueType.COMMUNITY,
                description='Standard BGP communities',
                action='attribute-add',
            ),
            'large-community': LeafList(
                type=ValueType.LARGE_COMMUNITY,
                description='Large BGP communities',
                action='attribute-add',
            ),
            'extended-community': LeafList(
                type=ValueType.EXTENDED_COMMUNITY,
                description='Extended BGP communities',
                action='attribute-add',
            ),
            'aigp': Leaf(
                type=ValueType.INTEGER,
                description='Accumulated IGP metric',
                action='attribute-add',
            ),
            'attribute': Leaf(
                type=ValueType.HEX_STRING,
                description='Generic BGP attribute',
                action='attribute-add',
            ),
            'name': Leaf(
                type=ValueType.STRING,
                description='Route name',
                action='attribute-add',
            ),
            'split': Leaf(
                type=ValueType.INTEGER,
                description='Split prefix',
                action='attribute-add',
            ),
            'watchdog': Leaf(
                type=ValueType.STRING,
                description='Watchdog name',
                action='attribute-add',
            ),
            'withdraw': Leaf(
                type=ValueType.BOOLEAN,
                description='Mark for withdrawal',
                action='attribute-add',
            ),
        },
    )

    name = 'ip'

    @property
    def syntax(self) -> str:
        """Syntax generated from schema."""
        return self.schema.syntax

    def __init__(self, parser: Parser, scope: Scope, error: Error) -> None:
        ParseAnnounce.__init__(self, parser, scope, error)

    def clear(self) -> None:
        pass

    def pre(self) -> bool:
        return True

    def post(self) -> bool:
        return ParseAnnounce.post(self) and self._check()

    @staticmethod
    def check(route: Route, afi: AFI | None) -> bool:
        if (
            route.action == Action.ANNOUNCE
            and route.nexthop is IP.NoNextHop
            and route.nlri.afi == afi
            and route.nlri.safi in (SAFI.unicast, SAFI.multicast)
        ):
            return False

        return True


@ParseAnnounce.register('multicast', 'extend-name', 'ipv4')
def multicast_v4(tokeniser: Tokeniser) -> list[Route]:
    return _build_route(tokeniser, AnnounceIP.schema, AFI.ipv4, SAFI.multicast)


@ParseAnnounce.register('multicast', 'extend-name', 'ipv6')
def multicast_v6(tokeniser: Tokeniser) -> list[Route]:
    return _build_route(tokeniser, AnnounceIP.schema, AFI.ipv6, SAFI.multicast)
