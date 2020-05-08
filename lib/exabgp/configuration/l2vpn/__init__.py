# encoding: utf-8
"""
l2vpn/__init__.py

Created by Thomas Mangin on 2015-06-04.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from exabgp.configuration.l2vpn.vpls import ParseVPLS

from exabgp.bgp.message.update.nlri import VPLS
from exabgp.bgp.message.update.attribute import Attributes
from exabgp.rib.change import Change

from exabgp.configuration.announce import ParseAnnounce


class ParseL2VPN(ParseVPLS):
    syntax = 'vpls %s;\n' % ' '.join(ParseVPLS.definition)

    action = dict(ParseVPLS.action)

    name = 'L2VPN'

    def __init__(self, tokeniser, scope, error, logger):
        ParseVPLS.__init__(self, tokeniser, scope, error, logger)

    def clear(self):
        return True

    def pre(self):
        return True

    def post(self):
        routes = self.scope.pop_routes()
        if routes:
            self.scope.extend('routes', routes)
        return True


@ParseL2VPN.register('vpls', 'append-route')
def vpls(tokeniser):
    change = Change(VPLS(None, None, None, None, None), Attributes())

    while True:
        command = tokeniser()

        if not command:
            break

        action = ParseVPLS.action[command]

        if 'nlri-set' in action:
            change.nlri.assign(ParseVPLS.assign[command], ParseL2VPN.known[command](tokeniser))
        elif 'attribute-add' in action:
            change.attributes.add(ParseL2VPN.known[command](tokeniser))
        elif action == 'nexthop-and-attribute':
            nexthop, attribute = ParseVPLS.known[command](tokeniser)
            change.nlri.nexthop = nexthop
            change.attributes.add(attribute)
        else:
            raise ValueError('vpls: unknown command "%s"' % command)

    return [
        change,
    ]
