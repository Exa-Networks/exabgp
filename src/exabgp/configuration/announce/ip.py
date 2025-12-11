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
from exabgp.configuration.schema import (
    RouteBuilder,
    Leaf,
    LeafList,
    ValueType,
    ActionTarget,
    ActionOperation,
    ActionKey,
)

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
                target=ActionTarget.NEXTHOP_ATTRIBUTE,
                operation=ActionOperation.SET,
                key=ActionKey.COMMAND,
            ),
            'origin': Leaf(
                type=ValueType.ORIGIN,
                description='BGP origin attribute',
                choices=['igp', 'egp', 'incomplete'],
                target=ActionTarget.ATTRIBUTE,
                operation=ActionOperation.ADD,
                key=ActionKey.NAME,
            ),
            'med': Leaf(
                type=ValueType.MED,
                description='Multi-exit discriminator',
                target=ActionTarget.ATTRIBUTE,
                operation=ActionOperation.ADD,
                key=ActionKey.NAME,
            ),
            'as-path': LeafList(
                type=ValueType.AS_PATH,
                description='AS path',
                target=ActionTarget.ATTRIBUTE,
                operation=ActionOperation.ADD,
                key=ActionKey.NAME,
            ),
            'local-preference': Leaf(
                type=ValueType.LOCAL_PREF,
                description='Local preference',
                target=ActionTarget.ATTRIBUTE,
                operation=ActionOperation.ADD,
                key=ActionKey.NAME,
            ),
            'atomic-aggregate': Leaf(
                type=ValueType.ATOMIC_AGGREGATE,
                description='Atomic aggregate flag',
                target=ActionTarget.ATTRIBUTE,
                operation=ActionOperation.ADD,
                key=ActionKey.NAME,
            ),
            'aggregator': Leaf(
                type=ValueType.AGGREGATOR,
                description='Aggregator (AS number and IP)',
                target=ActionTarget.ATTRIBUTE,
                operation=ActionOperation.ADD,
                key=ActionKey.NAME,
            ),
            'originator-id': Leaf(
                type=ValueType.IP_ADDRESS,
                description='Originator ID',
                target=ActionTarget.ATTRIBUTE,
                operation=ActionOperation.ADD,
                key=ActionKey.NAME,
            ),
            'cluster-list': LeafList(
                type=ValueType.IP_ADDRESS,
                description='Cluster list',
                target=ActionTarget.ATTRIBUTE,
                operation=ActionOperation.ADD,
                key=ActionKey.NAME,
            ),
            'community': LeafList(
                type=ValueType.COMMUNITY,
                description='Standard BGP communities',
                target=ActionTarget.ATTRIBUTE,
                operation=ActionOperation.ADD,
                key=ActionKey.NAME,
            ),
            'large-community': LeafList(
                type=ValueType.LARGE_COMMUNITY,
                description='Large BGP communities',
                target=ActionTarget.ATTRIBUTE,
                operation=ActionOperation.ADD,
                key=ActionKey.NAME,
            ),
            'extended-community': LeafList(
                type=ValueType.EXTENDED_COMMUNITY,
                description='Extended BGP communities',
                target=ActionTarget.ATTRIBUTE,
                operation=ActionOperation.ADD,
                key=ActionKey.NAME,
            ),
            'aigp': Leaf(
                type=ValueType.INTEGER,
                description='Accumulated IGP metric',
                target=ActionTarget.ATTRIBUTE,
                operation=ActionOperation.ADD,
                key=ActionKey.NAME,
            ),
            'attribute': Leaf(
                type=ValueType.HEX_STRING,
                description='Generic BGP attribute',
                target=ActionTarget.ATTRIBUTE,
                operation=ActionOperation.ADD,
                key=ActionKey.NAME,
            ),
            'name': Leaf(
                type=ValueType.STRING,
                description='Route name',
                target=ActionTarget.ATTRIBUTE,
                operation=ActionOperation.ADD,
                key=ActionKey.NAME,
            ),
            'split': Leaf(
                type=ValueType.INTEGER,
                description='Split prefix',
                target=ActionTarget.ATTRIBUTE,
                operation=ActionOperation.ADD,
                key=ActionKey.NAME,
            ),
            'watchdog': Leaf(
                type=ValueType.STRING,
                description='Watchdog name',
                target=ActionTarget.ATTRIBUTE,
                operation=ActionOperation.ADD,
                key=ActionKey.NAME,
            ),
            'withdraw': Leaf(
                type=ValueType.BOOLEAN,
                description='Mark for withdrawal',
                target=ActionTarget.ATTRIBUTE,
                operation=ActionOperation.ADD,
                key=ActionKey.NAME,
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


@ParseAnnounce.register_family(AFI.ipv4, SAFI.multicast, ActionTarget.SCOPE, ActionOperation.EXTEND, ActionKey.NAME)
def multicast_v4(tokeniser: Tokeniser) -> list[Route]:
    return _build_route(tokeniser, AnnounceIP.schema, AFI.ipv4, SAFI.multicast)


@ParseAnnounce.register_family(AFI.ipv6, SAFI.multicast, ActionTarget.SCOPE, ActionOperation.EXTEND, ActionKey.NAME)
def multicast_v6(tokeniser: Tokeniser) -> list[Route]:
    return _build_route(tokeniser, AnnounceIP.schema, AFI.ipv6, SAFI.multicast)
