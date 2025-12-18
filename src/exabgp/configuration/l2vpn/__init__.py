"""l2vpn/__init__.py

Created by Thomas Mangin on 2015-06-04.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from exabgp.configuration.l2vpn.vpls import ParseVPLS
from exabgp.configuration.schema import ActionTarget, ActionOperation, Container, RouteBuilder
from exabgp.protocol.family import AFI, SAFI
from exabgp.configuration.validator import RouteBuilderValidator
from exabgp.rib.route import Route

if TYPE_CHECKING:
    from exabgp.configuration.core.error import Error
    from exabgp.configuration.core.parser import Parser, Tokeniser
    from exabgp.configuration.core.scope import Scope

__all__ = [
    'ParseL2VPN',
    'ParseVPLS',
]


class ParseL2VPN(ParseVPLS):
    syntax = 'vpls {};\n'.format(' '.join(ParseVPLS.definition))

    # Schema: inherit parent schema and add vpls subsection
    # Must use RouteBuilder to match parent type (RouteBuilder extends Container)
    schema = RouteBuilder(
        description='L2VPN configuration',
        nlri_class=ParseVPLS.schema.nlri_class,
        settings_class=ParseVPLS.schema.settings_class,
        prefix_parser=ParseVPLS.schema.prefix_parser,
        assign=ParseVPLS.schema.assign,
        children={
            **ParseVPLS.schema.children,
            'vpls': Container(description='VPLS instance configuration'),
        },
    )

    action = dict(ParseVPLS.action)

    name = 'L2VPN'

    def __init__(self, parser: 'Parser', scope: 'Scope', error: 'Error') -> None:
        ParseVPLS.__init__(self, parser, scope, error)

    def clear(self) -> None:
        pass

    def pre(self) -> bool:
        return True

    def post(self) -> bool:
        routes = self.scope.pop_routes()
        if routes:
            self.scope.extend('routes', routes)
        return True


@ParseL2VPN.register_family(AFI.undefined, SAFI.vpls, ActionTarget.ROUTE, ActionOperation.EXTEND)
def vpls(tokeniser: 'Tokeniser') -> list[Route]:
    """Build VPLS route using RouteBuilderValidator with ParseVPLS schema."""
    validator = RouteBuilderValidator(schema=ParseVPLS.schema)
    return validator.validate(tokeniser)
