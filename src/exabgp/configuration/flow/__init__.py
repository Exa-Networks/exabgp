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
from exabgp.configuration.schema import ActionKey, ActionOperation, ActionTarget, Container, Leaf, LeafList

from exabgp.configuration.flow.route import ParseFlowRoute
from exabgp.configuration.flow.route import ParseFlowMatch
from exabgp.configuration.flow.route import ParseFlowThen
from exabgp.configuration.flow.route import ParseFlowScope

from exabgp.rib.route import Route
from exabgp.bgp.message.update.nlri import Flow
from exabgp.bgp.message.update.attribute import AttributeCollection
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
    def _get_route_action_enums(
        cls, command: str
    ) -> tuple[ActionTarget, ActionOperation, ActionKey, str | None] | None:
        """Get action enums for a flow route command from schema."""
        child = cls._route_schema_children.get(command)
        if isinstance(child, (Leaf, LeafList)):
            target, operation, key = child.get_action_enums()
            field_name = child.field_name if hasattr(child, 'field_name') else None
            return (target, operation, key, field_name)
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


@ParseFlow.register_command('route', ActionTarget.ROUTE, ActionOperation.EXTEND)
def route(tokeniser: Any) -> list[Route]:
    from exabgp.bgp.message import Action
    from exabgp.protocol.ip import IP

    flow_nlri = Flow.make_flow()
    flow_nlri.action = Action.ANNOUNCE  # Flow routes are always announcements
    attributes = AttributeCollection()
    nexthop: IP = IP.NoNextHop  # Track nexthop separately

    while True:
        command: str = tokeniser()

        if not command:
            break

        action_enums = ParseFlow._get_route_action_enums(command)
        if action_enums is None:
            raise ValueError(f'flow route: unknown command "{command}"')

        target, operation, key, field_name = action_enums

        if target == ActionTarget.NLRI:
            handler = cast(Callable[[Any], Any], ParseFlow.known[command])
            for adding in handler(tokeniser):
                flow_nlri.add(adding)
        elif target == ActionTarget.ATTRIBUTE:
            handler = cast(Callable[[Any], Any], ParseFlow.known[command])
            attributes.add(handler(tokeniser))
        elif target == ActionTarget.NEXTHOP_ATTRIBUTE:
            handler = cast(Callable[[Any], Any], ParseFlow.known[command])
            nh: Any
            attribute: Any
            nh, attribute = handler(tokeniser)
            nexthop = nh
            flow_nlri.nexthop = nexthop
            attributes.add(attribute)
        elif operation == ActionOperation.NOP:
            pass  # yes nothing to do !
        else:
            raise ValueError(f'flow: unknown command "{command}"')

    # Recreate NLRI with correct SAFI if RD is present
    # (avoids SAFI mutation which is incompatible with class-level SAFI)
    if flow_nlri.rd is not RouteDistinguisher.NORD and flow_nlri.safi != SAFI.flow_vpn:
        new_nlri = Flow.make_flow(flow_nlri.afi, SAFI.flow_vpn, flow_nlri.action)
        # Transfer all data to new NLRI
        new_nlri._rd_override = flow_nlri._rd_override
        new_nlri._rules_cache = flow_nlri._rules_cache
        new_nlri._packed_stale = True
        new_nlri.nexthop = flow_nlri.nexthop
        flow_nlri = new_nlri

    # Create Route at the end with explicit nexthop
    return [Route(flow_nlri, attributes, nexthop=nexthop)]
