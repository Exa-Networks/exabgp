"""route.py

Created by Thomas Mangin on 2015-06-22.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from typing import Any, Callable

from exabgp.protocol.family import SAFI
from exabgp.bgp.message.update.nlri.qualifier import RouteDistinguisher

from exabgp.configuration.core import Section
from exabgp.configuration.core import Parser
from exabgp.configuration.core import Scope
from exabgp.configuration.core import Error
from exabgp.configuration.schema import Container, Leaf, ValueType

from exabgp.configuration.flow.match import ParseFlowMatch
from exabgp.configuration.flow.then import ParseFlowThen
from exabgp.configuration.flow.scope import ParseFlowScope

from exabgp.configuration.static.mpls import route_distinguisher

__all__ = ['ParseFlowRoute', 'ParseFlowMatch', 'ParseFlowThen', 'ParseFlowScope']

from exabgp.bgp.message.update.nlri.flow import Flow
from exabgp.configuration.flow.parser import flow
from exabgp.configuration.flow.parser import next_hop

from exabgp.logger import log, lazymsg


class ParseFlowRoute(Section):
    # Schema definition for FlowSpec route
    schema = Container(
        description='FlowSpec route definition',
        children={
            'rd': Leaf(
                type=ValueType.RD,
                description='Route distinguisher',
                action='nlri-set',
            ),
            'route-distinguisher': Leaf(
                type=ValueType.RD,
                description='Route distinguisher (alias for rd)',
                action='nlri-set',
            ),
            'next-hop': Leaf(
                type=ValueType.NEXT_HOP,
                description='Next-hop for redirect-to-nexthop',
                action='nlri-nexthop',
            ),
            'match': Container(description='FlowSpec match criteria'),
            'scope': Container(description='FlowSpec scope'),
            'then': Container(description='FlowSpec actions'),
        },
    )
    syntax: str = (
        'route give-me-a-name {{\n'
        '  (optional) rd 255.255.255.255:65535|65535:65536|65536:65535;\n'
        '  next-hop 1.2.3.4; (to use with redirect-to-nexthop)\n'
        '  {}\n'
        '  {}\n'
        '  {}\n'
        '}}\n'.format(
            '\n  '.join(ParseFlowMatch.syntax.split('\n')),
            '\n  '.join(ParseFlowScope.syntax.split('\n')),
            '\n  '.join(ParseFlowThen.syntax.split('\n')),
        )
    )

    known: dict[str | tuple[Any, ...], Callable[[Any], Any]] = {
        'rd': route_distinguisher,
        'route-distinguisher': route_distinguisher,
        'next-hop': next_hop,
    }

    action: dict[str | tuple[Any, ...], str] = {
        'rd': 'nlri-set',
        'route-distinguisher': 'nlri-set',
        'next-hop': 'nlri-nexthop',
    }

    assign: dict[str, str] = {
        'rd': 'rd',
        'route-distinguisher': 'rd',
    }

    name: str = 'flow/route'

    def __init__(self, parser: Parser, scope: Scope, error: Error) -> None:
        Section.__init__(self, parser, scope, error)

    def clear(self) -> None:
        pass

    def pre(self) -> bool:
        self.scope.append_route(flow(None))
        return True

    def post(self) -> bool:
        route: Any = self.scope.get_route()
        # Recreate NLRI with correct SAFI if RD is present
        # (avoids SAFI mutation which is incompatible with class-level SAFI)
        if route.nlri.rd is not RouteDistinguisher.NORD and route.nlri.safi != SAFI.flow_vpn:
            old_nlri = route.nlri
            new_nlri = Flow.make_flow(old_nlri.afi, SAFI.flow_vpn, old_nlri.action)
            # Transfer all data to new NLRI
            new_nlri._rd_override = old_nlri._rd_override
            new_nlri._rules_cache = old_nlri._rules_cache
            new_nlri._packed_stale = True
            new_nlri.nexthop = old_nlri.nexthop
            route.nlri = new_nlri
        return True

    def _check(self, change: Any) -> bool:
        log.debug(lazymsg('flow.check status=not_implemented'), 'configuration')
        return True
