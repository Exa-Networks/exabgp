"""l2vpn/__init__.py

Created by Thomas Mangin on 2015-06-04.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from exabgp.configuration.l2vpn.vpls import ParseVPLS
from exabgp.configuration.schema import Container, ActionTarget, ActionOperation
from exabgp.protocol.family import AFI, SAFI
from exabgp.configuration.validator import RouteBuilderValidator

__all__ = [
    'ParseL2VPN',
    'ParseVPLS',
]


class ParseL2VPN(ParseVPLS):
    syntax = 'vpls {};\n'.format(' '.join(ParseVPLS.definition))

    # Schema: inherit parent schema children and add vpls subsection
    schema = Container(
        description='L2VPN configuration',
        children={
            **ParseVPLS.schema.children,
            'vpls': Container(description='VPLS instance configuration'),
        },
    )

    action = dict(ParseVPLS.action)

    name = 'L2VPN'

    def __init__(self, parser, scope, error):
        ParseVPLS.__init__(self, parser, scope, error)

    def clear(self) -> None:
        pass

    def pre(self):
        return True

    def post(self):
        routes = self.scope.pop_routes()
        if routes:
            self.scope.extend('routes', routes)
        return True


@ParseL2VPN.register_family(AFI.undefined, SAFI.vpls, ActionTarget.ROUTE, ActionOperation.EXTEND)
def vpls(tokeniser):
    """Build VPLS route using RouteBuilderValidator with ParseVPLS schema."""
    validator = RouteBuilderValidator(schema=ParseVPLS.schema)
    return validator.validate(tokeniser)
