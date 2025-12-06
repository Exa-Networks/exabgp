"""__init__.py

Created by Thomas Mangin on 2015-06-04.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from typing import Any, Callable, cast

from exabgp.protocol.family import SAFI

from exabgp.configuration.core import Section
from exabgp.configuration.core import Parser
from exabgp.configuration.core import Scope
from exabgp.configuration.core import Error
from exabgp.configuration.schema import Container, Leaf, LeafList

from exabgp.configuration.flow.route import ParseFlowRoute
from exabgp.configuration.flow.route import ParseFlowMatch
from exabgp.configuration.flow.route import ParseFlowThen
from exabgp.configuration.flow.route import ParseFlowScope

from exabgp.rib.route import Route
from exabgp.bgp.message.update.nlri import Flow
from exabgp.bgp.message.update.attribute import Attributes
from exabgp.bgp.message.update.nlri.qualifier import RouteDistinguisher


class ParseFlow(Section):
    # Schema definition for FlowSpec section
    schema = Container(
        description='FlowSpec rules',
        children={
            'route': Container(
                description='FlowSpec route definition',
                children={
                    **ParseFlowMatch.schema.children,
                    **ParseFlowThen.schema.children,
                    **ParseFlowScope.schema.children,
                },
            ),
        },
    )
    parts: str = ';\\n  '.join(ParseFlowRoute.syntax.split('\\n'))
    syntax: str = f'flow {{\n  {parts}}}'

    name: str = 'flow'

    known: dict[str | tuple[Any, ...], object] = dict(ParseFlowMatch.known)
    known.update(ParseFlowThen.known)
    known.update(ParseFlowScope.known)

    # Route schema children for action lookup in route() function
    _route_schema_children = {
        **ParseFlowMatch.schema.children,
        **ParseFlowThen.schema.children,
        **ParseFlowScope.schema.children,
    }

    @classmethod
    def _get_route_action(cls, command: str) -> str | None:
        """Get action for a flow route command from schema."""
        child = cls._route_schema_children.get(command)
        if isinstance(child, (Leaf, LeafList)):
            return child.action
        return None

    def __init__(self, parser: Parser, scope: Scope, error: Error) -> None:
        Section.__init__(self, parser, scope, error)

    def clear(self) -> None:
        pass

    def pre(self) -> bool:
        return True

    def post(self) -> bool:
        self.scope.set_value('routes', self.scope.get_routes())
        return True

    def check(self) -> bool:
        return True


@ParseFlow.register('route', 'append-route')
def route(tokeniser: Any) -> list[Route]:
    flow_nlri = Flow.make_flow()
    flow_route: Route = Route(flow_nlri, Attributes())

    while True:
        command: str = tokeniser()

        if not command:
            break

        action = ParseFlow._get_route_action(command)
        if action is None:
            raise ValueError(f'flow route: unknown command "{command}"')

        if action == 'nlri-add':
            handler = cast(Callable[[Any], Any], ParseFlow.known[command])
            for adding in handler(tokeniser):
                flow_nlri.add(adding)
        elif action == 'attribute-add':
            handler = cast(Callable[[Any], Any], ParseFlow.known[command])
            flow_route.attributes.add(handler(tokeniser))
        elif action == 'nexthop-and-attribute':
            handler = cast(Callable[[Any], Any], ParseFlow.known[command])
            nexthop: Any
            attribute: Any
            nexthop, attribute = handler(tokeniser)
            flow_nlri.nexthop = nexthop
            flow_route.attributes.add(attribute)
        elif action == 'nop':
            pass  # yes nothing to do !
        else:
            raise ValueError(f'flow: unknown command "{command}"')

    if flow_nlri.rd is not RouteDistinguisher.NORD:
        flow_nlri.safi = SAFI.flow_vpn

    return [flow_route]
