"""family.py

Created by Thomas Mangin on 2015-06-04.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations


from exabgp.protocol.family import AFI
from exabgp.protocol.family import SAFI
from exabgp.bgp.message.update.nlri.flow import NLRI

from exabgp.configuration.core import Section
from exabgp.configuration.core import Parser
from exabgp.configuration.core import Scope
from exabgp.configuration.core import Error
from exabgp.configuration.schema import Container, Leaf, ValueType


class ParseFamily(Section):
    # Schema definition for address family configuration
    schema = Container(
        description='Address families to negotiate with the peer',
        children={
            'ipv4': Leaf(
                type=ValueType.ENUMERATION,
                description='IPv4 address family',
                choices=['unicast', 'multicast', 'nlri-mpls', 'mpls-vpn', 'mcast-vpn', 'flow', 'flow-vpn', 'mup'],
                action='append-command',
            ),
            'ipv6': Leaf(
                type=ValueType.ENUMERATION,
                description='IPv6 address family',
                choices=['unicast', 'nlri-mpls', 'mpls-vpn', 'mcast-vpn', 'mup', 'flow', 'flow-vpn'],
                action='append-command',
            ),
            'l2vpn': Leaf(
                type=ValueType.ENUMERATION,
                description='L2VPN address family',
                choices=['vpls', 'evpn'],
                action='append-command',
            ),
            'bgp-ls': Leaf(
                type=ValueType.ENUMERATION,
                description='BGP-LS address family',
                choices=['bgp-ls', 'bgp-ls-vpn'],
                action='append-command',
            ),
            'all': Leaf(
                type=ValueType.BOOLEAN,
                description='Announce all known address families',
                action='append-command',
            ),
        },
    )
    syntax = (
        'family {\n'
        '   all;      # default if not family block is present, announce all we know\n'
        '   \n'
        '   ipv4 unicast;\n'
        '   ipv4 multicast;\n'
        '   ipv4 nlri-mpls;\n'
        '   ipv4 mpls-vpn;\n'
        '   ipv4 mcast-vpn;\n'
        '   ipv4 mup;\n'
        '   ipv4 flow;\n'
        '   ipv4 flow-vpn;\n'
        '   ipv6 unicast;\n'
        '   ipv6 mcast-vpn;\n'
        '   ipv6 mup;\n'
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
            'mcast-vpn': (AFI.ipv4, SAFI.mcast_vpn),
            'flow': (AFI.ipv4, SAFI.flow_ip),
            'flow-vpn': (AFI.ipv4, SAFI.flow_vpn),
            'mup': (AFI.ipv4, SAFI.mup),
        },
        'ipv6': {
            'unicast': (AFI.ipv6, SAFI.unicast),
            'nlri-mpls': (AFI.ipv6, SAFI.nlri_mpls),
            'mpls-vpn': (AFI.ipv6, SAFI.mpls_vpn),
            'mcast-vpn': (AFI.ipv6, SAFI.mcast_vpn),
            'mup': (AFI.ipv6, SAFI.mup),
            'flow': (AFI.ipv6, SAFI.flow_ip),
            'flow-vpn': (AFI.ipv6, SAFI.flow_vpn),
        },
        'l2vpn': {
            'vpls': (AFI.l2vpn, SAFI.vpls),
            'evpn': (AFI.l2vpn, SAFI.evpn),
        },
        'bgp-ls': {
            'bgp-ls': (AFI.bgpls, SAFI.bgp_ls),
            'bgp-ls-vpn': (AFI.bgpls, SAFI.bgp_ls_vpn),
        },
    }

    action = {
        'ipv4': 'append-command',
        'ipv6': 'append-command',
        'l2vpn': 'append-command',
        'bgp-ls': 'append-command',
        'all': 'append-command',
    }

    name = 'family'

    def __init__(self, parser: Parser, scope: Scope, error: Error) -> None:
        Section.__init__(self, parser, scope, error)
        self.known = {
            'ipv4': self.ipv4,
            'ipv6': self.ipv6,
            'l2vpn': self.l2vpn,
            'bgp-ls': self.bgpls,
            'all': self.all,
        }
        self._all: bool = False
        self._seen: list[tuple[AFI, SAFI]] = []

    def clear(self) -> None:
        self._all = False
        self._seen = []

    def pre(self) -> bool:
        self.clear()
        return True

    def post(self) -> bool:
        return True

    def _family(self, tokeniser, afi: str) -> tuple[AFI, SAFI]:
        if self._all:
            raise ValueError('can not add any family once family all is set')

        safi = tokeniser().lower()

        pair = self.convert[afi].get(safi, None)
        if not pair:
            raise ValueError(f'invalid afi/safi pair {afi}/{safi}')
        if pair in self._seen:
            raise ValueError(f'duplicate afi/safi pair {afi}/{safi}')
        self._seen.append(pair)
        return pair

    def ipv4(self, tokeniser) -> tuple[AFI, SAFI]:
        return self._family(tokeniser, 'ipv4')

    def ipv6(self, tokeniser) -> tuple[AFI, SAFI]:
        return self._family(tokeniser, 'ipv6')

    def l2vpn(self, tokeniser) -> tuple[AFI, SAFI]:
        return self._family(tokeniser, 'l2vpn')

    def bgpls(self, tokeniser) -> tuple[AFI, SAFI]:
        return self._family(tokeniser, 'bgp-ls')

    def minimal(self, tokeniser) -> None:
        raise ValueError('family minimal is deprecated')

    def all(self, tokeniser) -> None:
        if self._all or self._seen:
            self.error.set('all can not be used with any other options')
            return
        self._all = True
        for pair in NLRI.known_families():
            self._seen.append(pair)


class ParseAddPath(ParseFamily):
    # Schema definition for ADD-PATH configuration (same structure as family)
    schema = Container(
        description='ADD-PATH address families to negotiate',
        children={
            'ipv4': Leaf(
                type=ValueType.ENUMERATION,
                description='IPv4 ADD-PATH family',
                choices=['unicast', 'multicast', 'nlri-mpls', 'mpls-vpn', 'mcast-vpn', 'flow', 'flow-vpn', 'mup'],
                action='append-command',
            ),
            'ipv6': Leaf(
                type=ValueType.ENUMERATION,
                description='IPv6 ADD-PATH family',
                choices=['unicast', 'nlri-mpls', 'mpls-vpn', 'mcast-vpn', 'mup', 'flow', 'flow-vpn'],
                action='append-command',
            ),
            'l2vpn': Leaf(
                type=ValueType.ENUMERATION,
                description='L2VPN ADD-PATH family',
                choices=['vpls', 'evpn'],
                action='append-command',
            ),
            'bgp-ls': Leaf(
                type=ValueType.ENUMERATION,
                description='BGP-LS ADD-PATH family',
                choices=['bgp-ls', 'bgp-ls-vpn'],
                action='append-command',
            ),
            'all': Leaf(
                type=ValueType.BOOLEAN,
                description='Enable ADD-PATH for all families',
                action='append-command',
            ),
        },
    )

    name = 'add-path'
