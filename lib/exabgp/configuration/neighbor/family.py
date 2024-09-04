# encoding: utf-8
"""
family.py

Created by Thomas Mangin on 2015-06-04.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from exabgp.protocol.family import AFI
from exabgp.protocol.family import SAFI
from exabgp.bgp.message.update.nlri.flow import NLRI

from exabgp.configuration.core import Section


class ParseFamily(Section):
    syntax = (
        'family {\n'
        '   all;      # default if not family block is present, announce all we know\n'
        '   \n'
        '   ipv4 unicast;\n'
        '   ipv4 multicast;\n'
        '   ipv4 nlri-mpls;\n'
        '   ipv4 mpls-vpn;\n'
        '   ipv4 flow;\n'
        '   ipv4 flow-vpn;\n'
        '   ipv6 unicast;\n'
        '   ipv6 flow;\n'
        '   ipv6 flow-vpn;\n'
        '   l2vpn vpls;\n'
        '   l2vpn evpn;\n'
        '}'
    )

    convert = {
        'ipv4': {
            'unicast': (AFI.ipv4, SAFI.unicast),
            'multicast': (AFI.ipv4, SAFI.multicast),
            'nlri-mpls': (AFI.ipv4, SAFI.nlri_mpls),
            'mpls-vpn': (AFI.ipv4, SAFI.mpls_vpn),
            'flow': (AFI.ipv4, SAFI.flow_ip),
            'flow-vpn': (AFI.ipv4, SAFI.flow_vpn),
        },
        'ipv6': {
            'unicast': (AFI.ipv6, SAFI.unicast),
            'nlri-mpls': (AFI.ipv6, SAFI.nlri_mpls),
            'mpls-vpn': (AFI.ipv6, SAFI.mpls_vpn),
            'flow': (AFI.ipv6, SAFI.flow_ip),
            'flow-vpn': (AFI.ipv6, SAFI.flow_vpn),
        },
        'l2vpn': {'vpls': (AFI.l2vpn, SAFI.vpls), 'evpn': (AFI.l2vpn, SAFI.evpn),},
        'bgp-ls': {'bgp-ls': (AFI.bgpls, SAFI.bgp_ls), 'bgp-ls-vpn': (AFI.bgpls, SAFI.bgp_ls_vpn),},
    }

    action = {
        'ipv4': 'append-command',
        'ipv6': 'append-command',
        'l2vpn': 'append-command',
        'bgp-ls': 'append-command',
    }

    name = 'family'

    def __init__(self, tokeniser, scope, error, logger):
        Section.__init__(self, tokeniser, scope, error, logger)
        self.known = {
            'ipv4': self.ipv4,
            'ipv6': self.ipv6,
            'l2vpn': self.l2vpn,
            'bgp-ls': self.bgpls,
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

    def _family(self, tokeniser, afi):
        if self._all:
            raise ValueError('can not add any family once family all is set')

        safi = tokeniser().lower()

        pair = self.convert[afi].get(safi, None)
        if not pair:
            raise ValueError('invalid afi/safi pair %s/%s' % (afi, safi))
        if pair in self._seen:
            raise ValueError('duplicate afi/safi pair %s/%s' % (afi, safi))
        self._seen.append(pair)
        return pair

    def ipv4(self, tokeniser):
        return self._family(tokeniser, 'ipv4')

    def ipv6(self, tokeniser):
        return self._family(tokeniser, 'ipv6')

    def l2vpn(self, tokeniser):
        return self._family(tokeniser, 'l2vpn')

    def bgpls(self, tokeniser):
        return self._family(tokeniser, 'bgp-ls')

    def minimal(self, tokeniser):
        raise ValueError('family minimal is deprecated')

    def all(self, tokeniser):
        if self._all or self._seen:
            return self.error.set('all can not be used with any other options')
        self._all = True
        for pair in NLRI.known_families():
            self._seen.append(pair)


class ParseAddPath(ParseFamily):
    name = 'add-path'
