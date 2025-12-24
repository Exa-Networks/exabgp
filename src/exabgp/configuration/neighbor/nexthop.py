"""nexthop.py

Created by Thomas Mangin on 2019-05-23.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from typing import Any

from exabgp.protocol.family import AFI
from exabgp.protocol.family import SAFI

from exabgp.configuration.core import Section
from exabgp.configuration.core import Parser
from exabgp.configuration.core import Scope
from exabgp.configuration.core import Error
from exabgp.configuration.schema import ActionKey, ActionOperation, ActionTarget, Container, Leaf, ValueType
from exabgp.configuration.validator import NextHopTupleValidator, StatefulValidator, Validator


class ParseNextHop(Section):
    # Valid SAFI and next-hop AFI options for each AFI
    ipv4_config = {
        'safis': ['unicast', 'multicast', 'nlri-mpls', 'labeled-unicast', 'mpls-vpn'],
        'nhafis': ['ipv6'],
    }
    ipv6_config = {
        'safis': ['unicast', 'multicast', 'nlri-mpls', 'labeled-unicast', 'mpls-vpn'],
        'nhafis': ['ipv4'],
    }

    # Schema definition for nexthop encoding configuration
    schema = Container(
        description='Next-hop encoding options for address families',
        children={
            'ipv4': Leaf(
                type=ValueType.STRING,
                description='IPv4 SAFI with alternate next-hop AFI (e.g., "unicast ipv6")',
                target=ActionTarget.SCOPE,
                operation=ActionOperation.APPEND,
                key=ActionKey.COMMAND,
            ),
            'ipv6': Leaf(
                type=ValueType.STRING,
                description='IPv6 SAFI with alternate next-hop AFI (e.g., "unicast ipv4")',
                target=ActionTarget.SCOPE,
                operation=ActionOperation.APPEND,
                key=ActionKey.COMMAND,
            ),
        },
    )
    syntax = (
        'nexthop {\n'
        '   ipv4 unicast ipv6;\n'
        '   ipv4 multicast ipv6;\n'
        '   ipv4 mpls-vpn ipv6;\n'
        '   ipv4 nlri-mpls ipv6;\n'
        '   ipv6 unicast ipv4;\n'
        '   ipv6 multicast ipv4;\n'
        '   ipv6 mpls-vpn ipv4;\n'
        '   ipv6 labeled-unicast ipv4;  # preferred (nlri-mpls also accepted)\n'
        '}'
    )

    name = 'nexthop'

    def __init__(self, parser: Parser, scope: Scope, error: Error) -> None:
        Section.__init__(self, parser, scope, error)
        # Empty - all entries handled by schema validators via _get_stateful_validator
        self.known: dict[str | tuple[Any, ...], Any] = {}
        self._seen: set[tuple[AFI, SAFI, AFI]] = set()

    def clear(self) -> None:
        self._seen = set()

    def pre(self) -> bool:
        self.clear()
        return True

    def post(self) -> bool:
        return True

    def _get_stateful_validator(self, command: str) -> 'Validator[Any] | None':
        """Get stateful validator for nexthop commands with deduplication.

        This hook is called by Section.parse() before falling back to schema.
        It creates NextHopTupleValidator wrapped with StatefulValidator.
        """
        if command == 'ipv4':
            config = self.ipv4_config
        elif command == 'ipv6':
            config = self.ipv6_config
        else:
            return None

        # Create NextHopTupleValidator for 2-token parsing (safi + nhafi)
        inner = NextHopTupleValidator(
            afi=command,
            valid_safis=config['safis'],
            valid_nhafis=config['nhafis'],
        )

        # Wrap with StatefulValidator for deduplication using instance's _seen
        return StatefulValidator(inner=inner, seen=self._seen)
