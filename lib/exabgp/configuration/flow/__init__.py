# encoding: utf-8
"""
__init__.py

Created by Thomas Mangin on 2015-06-04.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from exabgp.protocol.family import SAFI

from exabgp.configuration.core import Section

from exabgp.configuration.flow.route import ParseFlowRoute
from exabgp.configuration.flow.route import ParseFlowMatch
from exabgp.configuration.flow.route import ParseFlowThen
from exabgp.configuration.flow.route import ParseFlowScope

from exabgp.rib.change import Change
from exabgp.bgp.message.update.nlri import Flow
from exabgp.bgp.message.update.attribute import Attributes
from exabgp.bgp.message.update.nlri.qualifier import RouteDistinguisher


class ParseFlow(Section):
    syntax = 'flow {\n' '  %s' '}' % ';\n  '.join(ParseFlowRoute.syntax.split('\n'))

    name = 'flow'

    known = dict(ParseFlowMatch.known)
    known.update(ParseFlowThen.known)
    known.update(ParseFlowScope.known)

    action = dict(ParseFlowMatch.action)
    action.update(ParseFlowThen.action)
    action.update(ParseFlowScope.action)

    def __init__(self, tokeniser, scope, error, logger):
        Section.__init__(self, tokeniser, scope, error, logger)

    def clear(self):
        pass

    def pre(self):
        return True

    def post(self):
        self.scope.set('routes', self.scope.get_routes())
        return True

    def check(self):
        return True


@ParseFlow.register('route', 'append-route')
def route(tokeniser):
    change = Change(Flow(), Attributes())

    while True:
        command = tokeniser()

        if not command:
            break

        action = ParseFlow.action[command]

        if action == 'nlri-add':
            for adding in ParseFlow.known[command](tokeniser):
                change.nlri.add(adding)
        elif action == 'attribute-add':
            change.attributes.add(ParseFlow.known[command](tokeniser))
        elif action == 'nexthop-and-attribute':
            nexthop, attribute = ParseFlow.known[command](tokeniser)
            change.nlri.nexthop = nexthop
            change.attributes.add(attribute)
        elif action == 'nop':
            pass  # yes nothing to do !
        else:
            raise ValueError('flow: unknown command "%s"' % command)

    if change.nlri.rd is not RouteDistinguisher.NORD:
        change.nlri.safi = SAFI.flow_vpn

    return [change]
