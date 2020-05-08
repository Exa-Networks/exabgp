# encoding: utf-8
"""
family.py

Created by Thomas Mangin on 2019-05-23.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from exabgp.protocol.family import AFI
from exabgp.protocol.family import SAFI
from exabgp.bgp.message.update.nlri.flow import NLRI

from exabgp.configuration.core import Section
from exabgp.configuration.neighbor.family import ParseFamily


class ParseNextHop(Section):
    syntax = (
        'nexthop {\n'
        '   ipv4 unicast ipv6;\n'
        '   ipv4 multicast ipv6;\n'
        '   ipv4 mpls-vpn ipv6;\n'
        '   ipv4 nlri-mpls ipv6;\n'
        '   ipv6 unicast ipv4;\n'
        '   ipv6 multicast ipv4;\n'
        '   ipv6 mpls-vpn ipv4;\n'
        '   ipv6 nlri-mpls ipv4;\n'
        '}'
    )

    convert = ParseFamily.convert

    action = {
        'ipv4': 'append-command',
        'ipv6': 'append-command',
    }

    name = 'nexthop'

    def __init__(self, tokeniser, scope, error, logger):
        Section.__init__(self, tokeniser, scope, error, logger)
        self.known = {
            'ipv4': self.ipv4,
            'ipv6': self.ipv6,
        }
        self._all = ''
        self._seen = []

    def clear(self):
        self._all = False
        self._seen = []

    def pre(self):
        self.clear()
        return True

    def post(self):
        return True

    def _family(self, tokeniser, afi, safis, nhafis):
        safi = tokeniser().lower()
        if safi not in safis:
            raise ValueError('invalid afi/safi pair %s/%s' % (afi, safi))

        nhafi = tokeniser().lower()
        if nhafi not in nhafis:
            raise ValueError('invalid nexthop afi %s' % nhafi)

        seen = (AFI.fromString(afi), SAFI.fromString(safi), AFI.fromString(nhafi))
        self._seen.append(seen)
        return seen

    def ipv4(self, tokeniser):
        return self._family(tokeniser, 'ipv4', ['unicast', 'multicast', 'nlri-mpls', 'mpls-vpn'], ['ipv6',])

    def ipv6(self, tokeniser):
        return self._family(tokeniser, 'ipv6', ['unicast', 'multicast', 'nlri-mpls', 'mpls-vpn'], ['ipv4',])
