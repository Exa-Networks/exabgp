"""route.py

Created by Thomas Mangin on 2015-06-22.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from typing import Any, Callable, Dict

from exabgp.protocol.family import SAFI
from exabgp.bgp.message.update.nlri.qualifier import RouteDistinguisher

from exabgp.configuration.core import Section
from exabgp.configuration.core import Parser
from exabgp.configuration.core import Scope
from exabgp.configuration.core import Error

from exabgp.configuration.flow.match import ParseFlowMatch
from exabgp.configuration.flow.then import ParseFlowThen
from exabgp.configuration.flow.scope import ParseFlowScope

from exabgp.configuration.static.mpls import route_distinguisher

from exabgp.configuration.flow.parser import flow
from exabgp.configuration.flow.parser import next_hop

from exabgp.logger import log, lazymsg


class ParseFlowRoute(Section):
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

    known: Dict[str | tuple[Any, ...], Callable[[Any], Any]] = {
        'rd': route_distinguisher,
        'route-distinguisher': route_distinguisher,
        'next-hop': next_hop,
    }

    action: Dict[str | tuple[Any, ...], str] = {
        'rd': 'nlri-set',
        'route-distinguisher': 'nlri-set',
        'next-hop': 'nlri-nexthop',
    }

    assign: Dict[str, str] = {
        'rd': 'rd',
        'route-distinguisher': 'rd',
    }

    name: str = 'flow/route'

    def __init__(self, parser: Parser, scope: Scope, error: Error) -> None:
        Section.__init__(self, parser, scope, error)

    def clear(self) -> None:
        pass

    def pre(self) -> bool:
        self.scope.append_route(flow(None))  # type: ignore[arg-type]
        return True

    def post(self) -> bool:
        route: Any = self.scope.get_route()
        if route.nlri.rd is not RouteDistinguisher.NORD:
            route.nlri.safi = SAFI.flow_vpn
        return True

    def _check(self, change: Any) -> bool:
        log.debug(lazymsg('flow.check status=not_implemented'), 'configuration')
        return True
