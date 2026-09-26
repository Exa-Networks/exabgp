"""route.py

Created by Thomas Mangin on 2015-06-22.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from exabgp.protocol.family import SAFI
from exabgp.bgp.message.update.nlri.qualifier import RouteDistinguisher

from exabgp.configuration.core import Section

from exabgp.configuration.flow.match import ParseFlowMatch
from exabgp.configuration.flow.then import ParseFlowThen
from exabgp.configuration.flow.scope import ParseFlowScope

from exabgp.configuration.static.mpls import route_distinguisher

from exabgp.configuration.flow.parser import flow
from exabgp.configuration.flow.parser import next_hop

from exabgp.logger import log


class ParseFlowRoute(Section):
    syntax = (
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

    def __init__(self, tokeniser, scope, error):
        Section.__init__(self, tokeniser, scope, error)

    def clear(self):
        pass

    def pre(self):
        self.scope.append_route(flow(None))
        return True

    def post(self):
        route = self.scope.get_route()

        # RFC 8955 4.2 encodes the value as `<[component]+>`, one component or more: the
        # components are individually optional, the list is not. The same section says an NLRI
        # "not encoded as specified here ... is considered malformed", so a rule with no match
        # is malformed on the wire and we must not build one.
        #
        # It is also the most dangerous thing we could emit. A packet matches "the intersection
        # (AND) of all the components present", and the intersection of nothing is every packet,
        # so `then { discard; }` with no match is discard-all. flow.py already refuses this
        # shape on the way IN, from a peer; until now we would announce what we would not
        # accept.
        if not route.nlri.rules:
            return self.error.set('a flow route needs at least one match, or it matches every packet')

        if route.nlri.rd is not RouteDistinguisher.NORD:
            route.nlri.safi = SAFI.flow_vpn
        return True

    def _check(self, change):
        log.debug(lambda: 'warning: no check on flows are implemented', 'configuration')
        return True
