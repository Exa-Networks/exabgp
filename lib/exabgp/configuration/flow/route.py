# encoding: utf-8
"""
route.py

Created by Thomas Mangin on 2015-06-22.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from exabgp.protocol.family import SAFI
from exabgp.bgp.message.update.nlri.qualifier import RouteDistinguisher

from exabgp.configuration.core import Section

from exabgp.configuration.flow.match import ParseFlowMatch
from exabgp.configuration.flow.then import ParseFlowThen
from exabgp.configuration.flow.scope import ParseFlowScope

from exabgp.configuration.static.mpls import route_distinguisher

from exabgp.configuration.flow.parser import flow
from exabgp.configuration.flow.parser import next_hop


class ParseFlowRoute(Section):
    syntax = (
        'route give-me-a-name {\n'
        '  (optional) rd 255.255.255.255:65535|65535:65536|65536:65535;\n'
        '  next-hop 1.2.3.4; (to use with redirect-to-nexthop)\n'
        '  %s\n'
        '  %s\n'
        '  %s\n'
        '}\n'
        % (
            '\n  '.join(ParseFlowMatch.syntax.split('\n')),
            '\n  '.join(ParseFlowScope.syntax.split('\n')),
            '\n  '.join(ParseFlowThen.syntax.split('\n')),
        )
    )

    known = {
        'rd': route_distinguisher,
        'route-distinguisher': route_distinguisher,
        'next-hop': next_hop,
    }

    action = {
        'rd': 'nlri-set',
        'route-distinguisher': 'nlri-set',
        'next-hop': 'nlri-nexthop',
    }

    assign = {
        'rd': 'rd',
        'route-distinguisher': 'rd',
    }

    name = 'flow/route'

    def __init__(self, tokeniser, scope, error, logger):
        Section.__init__(self, tokeniser, scope, error, logger)

    def clear(self):
        pass

    def pre(self):
        self.scope.append_route(flow(None))
        return True

    def post(self):
        route = self.scope.get_route()
        if route.nlri.rd is not RouteDistinguisher.NORD:
            route.nlri.safi = SAFI.flow_vpn
        return True

    def _check(self, change):
        self.logger.debug('warning: no check on flows are implemented', 'configuration')
        return True
