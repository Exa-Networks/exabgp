"""__init__.py

Created by Thomas Mangin on 2015-06-04.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from typing import Any, Dict, List

from exabgp.protocol.family import SAFI

from exabgp.configuration.core import Section
from exabgp.configuration.core import Tokeniser
from exabgp.configuration.core import Scope
from exabgp.configuration.core import Error

from exabgp.configuration.flow.route import ParseFlowRoute
from exabgp.configuration.flow.route import ParseFlowMatch
from exabgp.configuration.flow.route import ParseFlowThen
from exabgp.configuration.flow.route import ParseFlowScope

from exabgp.rib.change import Change
from exabgp.bgp.message.update.nlri import Flow
from exabgp.bgp.message.update.attribute import Attributes
from exabgp.bgp.message.update.nlri.qualifier import RouteDistinguisher


class ParseFlow(Section):
    parts: str = ';\\n  '.join(ParseFlowRoute.syntax.split('\\n'))
    syntax: str = f'flow {{\n  {parts}}}'

    name: str = 'flow'

    known: Dict[str | tuple[Any, ...], object] = dict(ParseFlowMatch.known)
    known.update(ParseFlowThen.known)
    known.update(ParseFlowScope.known)

    action: Dict[str | tuple[Any, ...], str] = dict(ParseFlowMatch.action)
    action.update(ParseFlowThen.action)
    action.update(ParseFlowScope.action)

    def __init__(self, tokeniser: Tokeniser, scope: Scope, error: Error) -> None:
        Section.__init__(self, tokeniser, scope, error)

    def clear(self) -> None:
        pass

    def pre(self) -> bool:
        return True

    def post(self) -> bool:
        self.scope.set('routes', self.scope.get_routes())
        return True

    def check(self) -> bool:
        return True


@ParseFlow.register('route', 'append-route')
def route(tokeniser: Any) -> List[Change]:
    change: Change = Change(Flow(), Attributes())

    while True:
        command: str = tokeniser()

        if not command:
            break

        action: str = ParseFlow.action[command]

        if action == 'nlri-add':
            for adding in ParseFlow.known[command](tokeniser):  # type: ignore[operator]
                change.nlri.add(adding)  # type: ignore[attr-defined]
        elif action == 'attribute-add':
            change.attributes.add(ParseFlow.known[command](tokeniser))  # type: ignore[operator]
        elif action == 'nexthop-and-attribute':
            nexthop: Any
            attribute: Any
            nexthop, attribute = ParseFlow.known[command](tokeniser)  # type: ignore[operator]
            change.nlri.nexthop = nexthop  # type: ignore[attr-defined]
            change.attributes.add(attribute)
        elif action == 'nop':
            pass  # yes nothing to do !
        else:
            raise ValueError(f'flow: unknown command "{command}"')

    if change.nlri.rd is not RouteDistinguisher.NORD:  # type: ignore[attr-defined]
        change.nlri.safi = SAFI.flow_vpn

    return [change]
