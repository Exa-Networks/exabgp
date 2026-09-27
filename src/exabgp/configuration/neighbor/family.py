"""family.py

Created by Thomas Mangin on 2015-06-04.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from dataclasses import dataclass, field
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

# RFC 4486 4: the Data field carries the upper bound in four octets
PREFIX_LIMIT_MAX = 0xFFFFFFFF


def family_name(family: FamilyTuple) -> str:
    return f'{family[0].name()} {family[1].name()}'


def prefix_limit(tokeniser: Tokeniser, family: FamilyTuple) -> int:
    """The `prefix-limit N` which may follow a family, or 0 when it does not."""
    keyword = tokeniser()
    if not keyword:
        return 0
    if keyword != 'prefix-limit':
        raise ValueError(
            f'unexpected token after {family_name(family)}: {keyword}\n'
            f'  Did you mean: {family_name(family)} prefix-limit <number>'
        )
    value = tokeniser()
    if not value:
        raise ValueError(f'prefix-limit requires a number\n  Example: {family_name(family)} prefix-limit 10000')
    if not value.isdigit():
        raise ValueError(f'prefix-limit must be a number, got: {value}')
    limit = int(value)
    if not 1 <= limit <= PREFIX_LIMIT_MAX:
        raise ValueError(f'prefix-limit must be 1-{PREFIX_LIMIT_MAX}, got {limit}')
    trailing = tokeniser()
    if trailing:
        raise ValueError(f'unexpected token after the prefix-limit of {family_name(family)}: {trailing}')
    return limit


@dataclass
class FamilyLineValidator(Validator[tuple[Any, ...]]):
    """A family, and the prefix-limit which may follow it, recorded on the side."""

    name: str = 'family'
    inner: Validator[tuple[Any, ...]] | None = None
    limits: dict[FamilyTuple, int] = field(default_factory=dict)

    def _parse(self, value: str) -> tuple[Any, ...]:
        assert self.inner is not None, 'FamilyLineValidator wraps the family validator'
        return self.inner._parse(value)

    def validate(self, tokeniser: Tokeniser) -> tuple[Any, ...]:
        assert self.inner is not None, 'FamilyLineValidator wraps the family validator'
        family = self.inner.validate(tokeniser)
        limit = prefix_limit(tokeniser, (family[0], family[1]))
        if limit:
            self.limits[(family[0], family[1])] = limit
        return family

    def to_schema(self) -> dict[str, Any]:
        assert self.inner is not None, 'FamilyLineValidator wraps the family validator'
        return self.inner.to_schema()


class ParseFamily(Section):
    # Families a neighbor without a family block does not negotiate: they have to be listed, or
    # asked for with `all`. RTC is one because negotiating it changes what the peer sends: a
    # route reflector following RFC 4684 section 6 sends no VPN route to a speaker which
    # negotiated RTC and announced no membership, so leaving it on by default emptied VPN feeds.
    listed_only: frozenset[FamilyTuple] = frozenset({(AFI.ipv4, SAFI.rtc)})

    @classmethod
    def default_families(cls) -> list[FamilyTuple]:
        """The families of a neighbor with no family block: every known one, less listed_only."""
        return [family for family in NLRI.known_families() if family not in cls.listed_only]

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
            'sr-policy': (AFI.ipv4, SAFI.sr_policy),
            'rtc': (AFI.ipv4, SAFI.rtc),
        },
        'ipv6': {
            'unicast': (AFI.ipv6, SAFI.unicast),
            'nlri-mpls': (AFI.ipv6, SAFI.nlri_mpls),
            'labeled-unicast': (AFI.ipv6, SAFI.nlri_mpls),  # preferred alias
            'mpls-vpn': (AFI.ipv6, SAFI.mpls_vpn),
            'mcast-vpn': (AFI.ipv6, SAFI.mcast_vpn),
            'mup': (AFI.ipv6, SAFI.mup),
            'sr-policy': (AFI.ipv6, SAFI.sr_policy),
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
                    'sr-policy',
                    'rtc',
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
                choices=[
                    'unicast',
                    'nlri-mpls',
                    'labeled-unicast',
                    'mpls-vpn',
                    'mcast-vpn',
                    'mup',
                    'sr-policy',
                    'flow',
                    'flow-vpn',
                ],
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
        '   all;      # announce all we know (no family block: all but ipv4 rtc)\n'
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
        '   \n'
        '   ipv4 unicast prefix-limit 10000;  # Cease (6,1) past 10000 routes\n'
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
        self._prefix_limit: dict[FamilyTuple, int] = {}

    def clear(self) -> None:
        self._all = False
        self._seen = set()
        self._prefix_limit = {}

    def pre(self) -> bool:
        self.clear()
        return True

    def post(self) -> bool:
        # A list of pairs rather than a dict: the scope is exported as JSON, which has no
        # tuple keys
        if self._prefix_limit:
            self.scope.set_value('prefix-limit', list(self._prefix_limit.items()))
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
        return FamilyLineValidator(inner=StatefulValidator(inner=inner, seen=self._seen), limits=self._prefix_limit)

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
        description='ADD-PATH address families to negotiate (with optional paths-limit)',
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
                    'sr-policy',
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
                choices=[
                    'unicast',
                    'nlri-mpls',
                    'labeled-unicast',
                    'mpls-vpn',
                    'mcast-vpn',
                    'mup',
                    'sr-policy',
                    'flow',
                    'flow-vpn',
                ],
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

    syntax = (
        'add-path {\n   ipv4 unicast;\n   ipv4 unicast limit 10;   # with PATHS-LIMIT\n   ipv6 unicast limit 20;\n}'
    )

    name = 'add-path'

    def __init__(self, parser: Parser, scope: Scope, error: Error) -> None:
        Section.__init__(self, parser, scope, error)
        self.known: dict[str | tuple[Any, ...], Any] = {'all': self.all}
        for afi_name in self.convert:
            self.known[afi_name] = partial(self._parse_addpath_family, afi_name=afi_name)
        self._all: bool = False
        self._seen: set[FamilyTuple] = set()

    def _parse_addpath_family(self, tokeniser: Tokeniser, afi_name: str) -> tuple[FamilyTuple, int]:
        safi_name = tokeniser()
        if not safi_name:
            raise ValueError(f'add-path {afi_name} requires a SAFI\n  Example: {afi_name} unicast')

        afi_safis = self.convert.get(afi_name)
        if afi_safis is None:
            raise ValueError(f'unknown AFI: {afi_name}')

        family = afi_safis.get(safi_name)
        if family is None:
            valid = ', '.join(sorted(afi_safis.keys()))
            raise ValueError(f'unknown SAFI for {afi_name}: {safi_name}\n  Valid: {valid}')

        if self._all:
            raise ValueError('cannot add specific families after "all"')
        if family in self._seen:
            raise ValueError(f'duplicate add-path entry for {afi_name} {safi_name}')
        self._seen.add(family)

        limit = 0
        next_token = tokeniser()
        if next_token == 'limit':
            limit_str = tokeniser()
            if not limit_str:
                raise ValueError(
                    f'add-path {afi_name} {safi_name} limit requires a value\n  Example: {afi_name} {safi_name} limit 10'
                )
            try:
                limit = int(limit_str)
            except ValueError:
                raise ValueError(f'paths-limit must be a number, got: {limit_str}')
            if not (1 <= limit <= 65535):
                raise ValueError(f'paths-limit must be 1-65535, got {limit}')
            trailing_token = tokeniser()
            if trailing_token:
                raise ValueError(f'unexpected token after paths-limit value: {trailing_token}')
        elif next_token:
            raise ValueError(
                f'unexpected token after {afi_name} {safi_name}: {next_token}\n  Did you mean: {afi_name} {safi_name} limit {next_token}'
            )

        return (family, limit)
