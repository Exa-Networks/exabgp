"""then.py

Created by Thomas Mangin on 2015-06-22.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from typing import Any

from exabgp.configuration.core import Section
from exabgp.configuration.core import Parser
from exabgp.configuration.core import Scope
from exabgp.configuration.core import Error
from exabgp.configuration.schema import Container, Leaf, LeafList, ValueType

from exabgp.configuration.flow.parser import accept
from exabgp.configuration.flow.parser import discard
from exabgp.configuration.flow.parser import rate_limit
from exabgp.configuration.flow.parser import redirect
from exabgp.configuration.flow.parser import redirect_next_hop
from exabgp.configuration.flow.parser import redirect_next_hop_ietf
from exabgp.configuration.flow.parser import copy
from exabgp.configuration.flow.parser import mark
from exabgp.configuration.flow.parser import action

from exabgp.configuration.static.parser import community
from exabgp.configuration.static.parser import large_community
from exabgp.configuration.static.parser import extended_community


class ParseFlowThen(Section):
    # Schema definition for FlowSpec actions
    schema = Container(
        description='FlowSpec actions to apply',
        children={
            'accept': Leaf(
                type=ValueType.BOOLEAN,
                description='Accept matching traffic',
                action='nop',
            ),
            'discard': Leaf(
                type=ValueType.BOOLEAN,
                description='Discard matching traffic',
                action='attribute-add',
            ),
            'rate-limit': Leaf(
                type=ValueType.INTEGER,
                description='Rate limit in bytes per second',
                action='attribute-add',
            ),
            'redirect': Leaf(
                type=ValueType.STRING,
                description='Redirect to VRF (route-target or IP)',
                action='nexthop-and-attribute',
            ),
            'redirect-to-nexthop': Leaf(
                type=ValueType.BOOLEAN,
                description='Redirect to next-hop',
                action='attribute-add',
            ),
            'redirect-to-nexthop-ietf': Leaf(
                type=ValueType.BOOLEAN,
                description='Redirect to next-hop (IETF format)',
                action='attribute-add',
            ),
            'copy': Leaf(
                type=ValueType.IP_ADDRESS,
                description='Copy to IP address',
                action='nexthop-and-attribute',
            ),
            'mark': Leaf(
                type=ValueType.INTEGER,
                description='Set DSCP marking',
                action='attribute-add',
            ),
            'action': Leaf(
                type=ValueType.ENUMERATION,
                description='Traffic action',
                choices=['sample', 'terminal', 'sample-terminal'],
                action='attribute-add',
            ),
            'community': LeafList(
                type=ValueType.COMMUNITY,
                description='Standard BGP communities',
                action='attribute-add',
            ),
            'large-community': LeafList(
                type=ValueType.LARGE_COMMUNITY,
                description='Large BGP communities',
                action='attribute-add',
            ),
            'extended-community': LeafList(
                type=ValueType.EXTENDED_COMMUNITY,
                description='Extended BGP communities',
                action='attribute-add',
            ),
        },
    )
    definition: list[str] = [
        'accept',
        'discard',
        'rate-limit 9600',
        'redirect 30740:12345',
        'redirect 1.2.3.4:5678',
        'redirect 1.2.3.4',
        'redirect-next-hop',
        'copy 1.2.3.4',
        'mark 123',
        'action sample|terminal|sample-terminal',
    ]

    joined: str = ';\\n  '.join(definition)
    syntax: str = f'then {{\n  {joined};\n}}'

    # Parser functions for flow 'then' actions
    # Each function takes a Tokeniser and returns various types (None, ExtendedCommunities, etc.)
    known: dict[str | tuple[Any, ...], object] = {
        'accept': accept,
        'discard': discard,
        'rate-limit': rate_limit,
        'redirect': redirect,
        'redirect-to-nexthop': redirect_next_hop,
        'redirect-to-nexthop-ietf': redirect_next_hop_ietf,
        'copy': copy,
        'mark': mark,
        'action': action,
        'community': community,
        'large-community': large_community,
        'extended-community': extended_community,
    }

    # 'community','extended-community'

    action: dict[str | tuple[Any, ...], str] = {
        'accept': 'nop',
        'discard': 'attribute-add',
        'rate-limit': 'attribute-add',
        'redirect': 'nexthop-and-attribute',
        'redirect-to-nexthop': 'attribute-add',
        'redirect-to-nexthop-ietf': 'attribute-add',
        'copy': 'nexthop-and-attribute',
        'mark': 'attribute-add',
        'action': 'attribute-add',
        'community': 'attribute-add',
        'large-community': 'attribute-add',
        'extended-community': 'attribute-add',
    }

    name: str = 'flow/then'

    def __init__(self, parser: Parser, scope: Scope, error: Error) -> None:
        Section.__init__(self, parser, scope, error)

    def clear(self) -> None:
        pass

    def pre(self) -> bool:
        return True

    def post(self) -> bool:
        return True
