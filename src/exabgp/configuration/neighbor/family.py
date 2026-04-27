"""family.py

Created by Thomas Mangin on 2015-06-04.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from functools import partial
from typing import Any

from exabgp.protocol.family import AFI, SAFI, FamilyTuple
from exabgp.bgp.message.update.nlri import NLRI

from exabgp.configuration.core import Section
from exabgp.configuration.core import Parser
from exabgp.configuration.core import Scope
from exabgp.configuration.core import Error
from exabgp.configuration.core import Tokeniser
from exabgp.configuration.schema import ActionKey, ActionOperation, ActionTarget, Container, Leaf, ValueType, TupleLeaf
from exabgp.configuration.validator import TupleValidator, StatefulValidator, Validator


class ParseFamily(Section):
    # Conversion map: AFI -> SAFI -> (AFI enum, SAFI enum) tuple
    convert = {
        'ipv4': {
            'unicast': (AFI.ipv4, SAFI.unicast),
            'multicast': (AFI.ipv4, SAFI.multicast),
            'nlri-mpls': (AFI.ipv4, SAFI.nlri_mpls),
            'labeled-unicast': (AFI.ipv4, SAFI.nlri_mpls),  # alias
            'mpls-vpn': (AFI.ipv4, SAFI.mpls_vpn),
            'mcast-vpn': (AFI.ipv4, SAFI.mcast_vpn),
            'flow': (AFI.ipv4, SAFI.flow_ip),
            'flow-vpn': (AFI.ipv4, SAFI.flow_vpn),
            'mup': (AFI.ipv4, SAFI.mup),
        },
        'ipv6': {
            'unicast': (AFI.ipv6, SAFI.unicast),
            'nlri-mpls': (AFI.ipv6, SAFI.nlri_mpls),
            'labeled-unicast': (AFI.ipv6, SAFI.nlri_mpls),  # preferred alias
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
                choices=[
                    'unicast',
                    'multicast',
                    'nlri-mpls',
                    'labeled-unicast',
                    'mpls-vpn',
                    'mcast-vpn',
                    'flow',
                    'flow-vpn',
                    'mup',
                ],
                conversion_map=convert,
                afi_context='ipv4',
                track_duplicates=True,
                target=ActionTarget.SCOPE,
                operation=ActionOperation.APPEND,
                key=ActionKey.COMMAND,
            ),
            'ipv6': TupleLeaf(
                type=ValueType.ENUMERATION,
                description='IPv6 address family',
                choices=['unicast', 'nlri-mpls', 'labeled-unicast', 'mpls-vpn', 'mcast-vpn', 'mup', 'flow', 'flow-vpn'],
                conversion_map=convert,
                afi_context='ipv6',
                track_duplicates=True,
                target=ActionTarget.SCOPE,
                operation=ActionOperation.APPEND,
                key=ActionKey.COMMAND,
            ),
            'l2vpn': TupleLeaf(
                type=ValueType.ENUMERATION,
                description='L2VPN address family',
                choices=['vpls', 'evpn'],
                conversion_map=convert,
                afi_context='l2vpn',
                track_duplicates=True,
                target=ActionTarget.SCOPE,
                operation=ActionOperation.APPEND,
                key=ActionKey.COMMAND,
            ),
            'bgp-ls': TupleLeaf(
                type=ValueType.ENUMERATION,
                description='BGP-LS address family',
                choices=['bgp-ls', 'bgp-ls-vpn'],
                conversion_map=convert,
                afi_context='bgp-ls',
                track_duplicates=True,
                target=ActionTarget.SCOPE,
                operation=ActionOperation.APPEND,
                key=ActionKey.COMMAND,
            ),
            'all': Leaf(
                type=ValueType.BOOLEAN,
                description='Announce all known address families',
                target=ActionTarget.SCOPE,
                operation=ActionOperation.APPEND,
                key=ActionKey.COMMAND,
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
        '   ipv6 labeled-unicast;  # preferred (nlri-mpls also accepted)\n'
        '   ipv6 mpls-vpn;\n'
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
        self._seen: set[FamilyTuple] = set()

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

    def all(self, tokeniser: Tokeniser) -> None:
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
                choices=[
                    'unicast',
                    'multicast',
                    'nlri-mpls',
                    'labeled-unicast',
                    'mpls-vpn',
                    'mcast-vpn',
                    'flow',
                    'flow-vpn',
                    'mup',
                ],
                conversion_map=ParseFamily.convert,
                afi_context='ipv4',
                track_duplicates=True,
                target=ActionTarget.SCOPE,
                operation=ActionOperation.APPEND,
                key=ActionKey.COMMAND,
            ),
            'ipv6': TupleLeaf(
                type=ValueType.ENUMERATION,
                description='IPv6 ADD-PATH family',
                choices=['unicast', 'nlri-mpls', 'labeled-unicast', 'mpls-vpn', 'mcast-vpn', 'mup', 'flow', 'flow-vpn'],
                conversion_map=ParseFamily.convert,
                afi_context='ipv6',
                track_duplicates=True,
                target=ActionTarget.SCOPE,
                operation=ActionOperation.APPEND,
                key=ActionKey.COMMAND,
            ),
            'l2vpn': TupleLeaf(
                type=ValueType.ENUMERATION,
                description='L2VPN ADD-PATH family',
                choices=['vpls', 'evpn'],
                conversion_map=ParseFamily.convert,
                afi_context='l2vpn',
                track_duplicates=True,
                target=ActionTarget.SCOPE,
                operation=ActionOperation.APPEND,
                key=ActionKey.COMMAND,
            ),
            'bgp-ls': TupleLeaf(
                type=ValueType.ENUMERATION,
                description='BGP-LS ADD-PATH family',
                choices=['bgp-ls', 'bgp-ls-vpn'],
                conversion_map=ParseFamily.convert,
                afi_context='bgp-ls',
                track_duplicates=True,
                target=ActionTarget.SCOPE,
                operation=ActionOperation.APPEND,
                key=ActionKey.COMMAND,
            ),
            'all': Leaf(
                type=ValueType.BOOLEAN,
                description='Enable ADD-PATH for all families',
                target=ActionTarget.SCOPE,
                operation=ActionOperation.APPEND,
                key=ActionKey.COMMAND,
            ),
        },
    )

    name = 'add-path'


class ParsePathsLimit(Section):
    convert = ParseFamily.convert

    schema = Container(
        description='Per-family PATHS-LIMIT configuration',
        children={
            'all': Leaf(
                type=ValueType.INTEGER,
                description='Default paths-limit for all unspecified families',
                target=ActionTarget.SCOPE,
                operation=ActionOperation.SET,
                key=ActionKey.COMMAND,
            ),
            'ipv4': Leaf(
                type=ValueType.STRING,
                description='IPv4 paths-limit (e.g. "unicast 10")',
                target=ActionTarget.SCOPE,
                operation=ActionOperation.APPEND,
                key=ActionKey.COMMAND,
            ),
            'ipv6': Leaf(
                type=ValueType.STRING,
                description='IPv6 paths-limit (e.g. "unicast 20")',
                target=ActionTarget.SCOPE,
                operation=ActionOperation.APPEND,
                key=ActionKey.COMMAND,
            ),
            'l2vpn': Leaf(
                type=ValueType.STRING,
                description='L2VPN paths-limit',
                target=ActionTarget.SCOPE,
                operation=ActionOperation.APPEND,
                key=ActionKey.COMMAND,
            ),
            'bgp-ls': Leaf(
                type=ValueType.STRING,
                description='BGP-LS paths-limit',
                target=ActionTarget.SCOPE,
                operation=ActionOperation.APPEND,
                key=ActionKey.COMMAND,
            ),
        },
    )

    syntax = 'paths-limit {\n   all 10;\n   ipv4 unicast 32;\n   ipv6 mpls-vpn 0;\n}\n'

    name = 'paths-limit'

    def __init__(self, parser: Parser, scope: Scope, error: Error) -> None:
        Section.__init__(self, parser, scope, error)
        self.known = {'all': self._parse_all}
        for afi in self.convert:
            self.known[afi] = partial(self._parse_family_limit, afi_name=afi)
        self._seen: set[FamilyTuple] = set()
        self._all_set: bool = False

    def clear(self) -> None:
        self._seen = set()
        self._all_set = False

    def pre(self) -> bool:
        self.clear()
        return True

    def post(self) -> bool:
        return True

    def _parse_all(self, tokeniser: Tokeniser) -> int:
        if self._all_set:
            raise ValueError('duplicate "all" entry in paths-limit block')
        limit_str = tokeniser()
        if not limit_str:
            raise ValueError('paths-limit "all" requires a limit value\n  Example: all 10')
        try:
            limit = int(limit_str)
        except ValueError:
            raise ValueError(f'paths-limit "all" must be a number, got: {limit_str}')
        if not (0 <= limit <= 65535):
            raise ValueError(f'paths-limit "all" must be 0-65535, got {limit}')
        self._all_set = True
        return limit

    def _parse_family_limit(self, tokeniser: Tokeniser, afi_name: str) -> tuple[FamilyTuple, int]:
        safi_name = tokeniser()
        limit_str = tokeniser()

        if not safi_name or not limit_str:
            raise ValueError(f'paths-limit {afi_name} requires SAFI and limit value\n  Example: {afi_name} unicast 10')

        afi_safis = self.convert.get(afi_name)
        if afi_safis is None:
            raise ValueError(f'unknown AFI: {afi_name}')

        family = afi_safis.get(safi_name)
        if family is None:
            valid = ', '.join(sorted(afi_safis.keys()))
            raise ValueError(f'unknown SAFI for {afi_name}: {safi_name}\n  Valid: {valid}')

        try:
            limit = int(limit_str)
        except ValueError:
            raise ValueError(f'paths-limit must be a number, got: {limit_str}')

        if not (0 <= limit <= 65535):
            raise ValueError(f'paths-limit must be 0-65535, got {limit}')

        if family in self._seen:
            raise ValueError(f'duplicate paths-limit for {afi_name} {safi_name}')
        self._seen.add(family)

        return (family, limit)
