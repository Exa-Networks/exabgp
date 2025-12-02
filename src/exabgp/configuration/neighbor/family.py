"""family.py

Created by Thomas Mangin on 2015-06-04.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from typing import Any

from exabgp.protocol.family import AFI
from exabgp.protocol.family import SAFI
from exabgp.bgp.message.update.nlri.flow import NLRI

from exabgp.configuration.core import Section
from exabgp.configuration.core import Parser
from exabgp.configuration.core import Scope
from exabgp.configuration.core import Error
from exabgp.configuration.schema import Container, Leaf, ValueType, TupleLeaf
from exabgp.configuration.validator import TupleValidator, StatefulValidator, Validator


class ParseFamily(Section):
    # Conversion map: AFI -> SAFI -> (AFI enum, SAFI enum) tuple
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

    # Schema definition for address family configuration
    # Uses TupleLeaf for AFI commands that return (AFI, SAFI) tuples
    schema = Container(
        description='Address families to negotiate with the peer',
        children={
            'ipv4': TupleLeaf(
                type=ValueType.ENUMERATION,
                description='IPv4 address family',
                choices=['unicast', 'multicast', 'nlri-mpls', 'mpls-vpn', 'mcast-vpn', 'flow', 'flow-vpn', 'mup'],
                action='append-command',
                conversion_map=convert,
                afi_context='ipv4',
                track_duplicates=True,
            ),
            'ipv6': TupleLeaf(
                type=ValueType.ENUMERATION,
                description='IPv6 address family',
                choices=['unicast', 'nlri-mpls', 'mpls-vpn', 'mcast-vpn', 'mup', 'flow', 'flow-vpn'],
                action='append-command',
                conversion_map=convert,
                afi_context='ipv6',
                track_duplicates=True,
            ),
            'l2vpn': TupleLeaf(
                type=ValueType.ENUMERATION,
                description='L2VPN address family',
                choices=['vpls', 'evpn'],
                action='append-command',
                conversion_map=convert,
                afi_context='l2vpn',
                track_duplicates=True,
            ),
            'bgp-ls': TupleLeaf(
                type=ValueType.ENUMERATION,
                description='BGP-LS address family',
                choices=['bgp-ls', 'bgp-ls-vpn'],
                action='append-command',
                conversion_map=convert,
                afi_context='bgp-ls',
                track_duplicates=True,
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

    name = 'family'

    def __init__(self, parser: Parser, scope: Scope, error: Error) -> None:
        Section.__init__(self, parser, scope, error)
        # Only 'all' remains in known - AFI commands use schema validators
        self.known = {
            'all': self.all,
        }
        self._all: bool = False
        self._seen: set[tuple[AFI, SAFI]] = set()

    def clear(self) -> None:
        self._all = False
        self._seen = set()

    def pre(self) -> bool:
        self.clear()
        return True

    def post(self) -> bool:
        return True

    def _get_stateful_validator(self, command: str) -> 'Validator[Any] | None':
        """Get stateful validator for AFI commands with deduplication.

        This hook is called by Section.parse() before falling back to schema.
        It injects instance state (_seen, _all) into the validator chain.
        """
        # Check if 'all' was already set
        if self._all:
            raise ValueError('cannot add any family once family all is set')

        # Only handle AFI commands (ipv4, ipv6, l2vpn, bgp-ls)
        if command not in self.convert:
            return None

        # Get the TupleLeaf from schema
        child = self.schema.children.get(command)
        if not isinstance(child, TupleLeaf):
            return None

        # Create TupleValidator with the conversion map and AFI context
        inner = TupleValidator(
            conversion_map=child.conversion_map or {},
            afi_context=child.afi_context,
        )

        # Wrap with StatefulValidator for deduplication using instance's _seen
        return StatefulValidator(inner=inner, seen=self._seen)

    def all(self, tokeniser) -> None:
        """Handle 'all' command - enable all known address families."""
        if self._all or self._seen:
            self.error.set('all cannot be used with any other options')
            return
        self._all = True
        for pair in NLRI.known_families():
            self._seen.add(pair)


class ParseAddPath(ParseFamily):
    # Schema definition for ADD-PATH configuration
    # Uses TupleLeaf like ParseFamily - inherits _get_stateful_validator and convert
    schema = Container(
        description='ADD-PATH address families to negotiate',
        children={
            'ipv4': TupleLeaf(
                type=ValueType.ENUMERATION,
                description='IPv4 ADD-PATH family',
                choices=['unicast', 'multicast', 'nlri-mpls', 'mpls-vpn', 'mcast-vpn', 'flow', 'flow-vpn', 'mup'],
                action='append-command',
                conversion_map=ParseFamily.convert,
                afi_context='ipv4',
                track_duplicates=True,
            ),
            'ipv6': TupleLeaf(
                type=ValueType.ENUMERATION,
                description='IPv6 ADD-PATH family',
                choices=['unicast', 'nlri-mpls', 'mpls-vpn', 'mcast-vpn', 'mup', 'flow', 'flow-vpn'],
                action='append-command',
                conversion_map=ParseFamily.convert,
                afi_context='ipv6',
                track_duplicates=True,
            ),
            'l2vpn': TupleLeaf(
                type=ValueType.ENUMERATION,
                description='L2VPN ADD-PATH family',
                choices=['vpls', 'evpn'],
                action='append-command',
                conversion_map=ParseFamily.convert,
                afi_context='l2vpn',
                track_duplicates=True,
            ),
            'bgp-ls': TupleLeaf(
                type=ValueType.ENUMERATION,
                description='BGP-LS ADD-PATH family',
                choices=['bgp-ls', 'bgp-ls-vpn'],
                action='append-command',
                conversion_map=ParseFamily.convert,
                afi_context='bgp-ls',
                track_duplicates=True,
            ),
            'all': Leaf(
                type=ValueType.BOOLEAN,
                description='Enable ADD-PATH for all families',
                action='append-command',
            ),
        },
    )

    name = 'add-path'
