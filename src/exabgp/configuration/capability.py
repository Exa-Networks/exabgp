"""capability.py

Created by Thomas Mangin on 2015-06-04.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from exabgp.configuration.core.error import Error
    from exabgp.configuration.core.parser import Parser
    from exabgp.configuration.core.parser import Tokeniser
    from exabgp.configuration.core.scope import Scope

from exabgp.bgp.message.open.capability.graceful import Graceful

from exabgp.configuration.core import Section
from exabgp.configuration.parser import boolean
from exabgp.configuration.parser import string
from exabgp.configuration.schema import Container, Leaf, ValueType


def addpath(tokeniser: 'Tokeniser') -> int:
    if not tokeniser.tokens:
        raise ValueError('add-path requires a value\n  Valid options: send, receive, send/receive, disable')

    ap = string(tokeniser).lower()

    match = {
        'disable': 0,
        'disabled': 0,
        'receive': 1,
        'send': 2,
        'send/receive': 3,
    }

    if ap in match:
        return match[ap]

    if ap == 'receive/send':  # was allowed with the previous parser
        raise ValueError("'receive/send' is not valid\n  Did you mean: send/receive")

    raise ValueError(f"'{ap}' is not a valid add-path option\n  Valid options: send, receive, send/receive, disable")


def gracefulrestart(tokeniser: 'Tokeniser', default: int | bool) -> int | bool:
    if len(tokeniser.tokens) == 1:
        return default

    state = string(tokeniser)

    if state in ('disable', 'disabled'):
        return False

    try:
        grace = int(state)
    except ValueError:
        raise ValueError(
            f"'{state}' is not a valid graceful-restart time\n  Valid options: <seconds> (0-{Graceful.MAX}), disable"
        ) from None

    if grace < 0:
        raise ValueError(f"graceful-restart {grace} is invalid\n  Must be 0-{Graceful.MAX} seconds or 'disable'")
    if grace > Graceful.MAX:
        raise ValueError(f'graceful-restart {grace} is invalid\n  Maximum is {Graceful.MAX} seconds')

    return grace


class ParseCapability(Section):
    TTL_SECURITY = 255

    # Schema definition for BGP capabilities
    schema = Container(
        description='BGP capabilities to negotiate with the peer',
        children={
            'nexthop': Leaf(
                type=ValueType.BOOLEAN,
                description='Extended next-hop capability',
                default=True,
            ),
            'add-path': Leaf(
                type=ValueType.ENUMERATION,
                description='ADD-PATH capability mode',
                choices=['disable', 'receive', 'send', 'send/receive'],
            ),
            'asn4': Leaf(
                type=ValueType.BOOLEAN,
                description='4-byte AS number capability',
                default=True,
            ),
            'graceful-restart': Leaf(
                type=ValueType.INTEGER,
                description='Graceful restart time in seconds (0 to use hold-time, or "disable")',
                default=0,
                min_value=0,
                max_value=4095,
            ),
            'multi-session': Leaf(
                type=ValueType.BOOLEAN,
                description='Multi-session capability',
                default=True,
            ),
            'operational': Leaf(
                type=ValueType.BOOLEAN,
                description='Operational capability for advisory messages',
                default=True,
            ),
            'route-refresh': Leaf(
                type=ValueType.BOOLEAN,
                description='Route refresh capability',
                default=True,
            ),
            'aigp': Leaf(
                type=ValueType.BOOLEAN,
                description='AIGP (Accumulated IGP Metric) capability',
                default=True,
            ),
            'extended-message': Leaf(
                type=ValueType.BOOLEAN,
                description='Extended message capability (>4096 bytes)',
                default=True,
            ),
            'software-version': Leaf(
                type=ValueType.BOOLEAN,
                description='Software version capability',
                default=False,
            ),
        },
    )

    syntax = (
        'capability {\n'
        '   add-path disable|send|receive|send/receive;\n'
        '   asn4 enable|disable;\n'
        '   graceful-restart <time in second>;\n'
        '   multi-session enable|disable;\n'
        '   operational enable|disable;\n'
        '   refresh enable|disable;\n'
        '   extended-message enable|disable;\n'
        '   software-version enable|disable;\n'
        '}\n'
    )

    known = {
        'nexthop': boolean,
        'add-path': addpath,
        'asn4': boolean,
        'graceful-restart': gracefulrestart,
        'multi-session': boolean,
        'operational': boolean,
        'route-refresh': boolean,
        'aigp': boolean,
        'extended-message': boolean,
        'software-version': boolean,
    }

    # action dict removed - derived from schema (defaults to 'set-command')

    default = {
        'nexthop': True,
        'asn4': True,
        'graceful-restart': 0,
        'multi-session': True,
        'operational': True,
        'route-refresh': True,
        'aigp': True,
        'extended-message': True,
        'software-version': False,
    }

    name = 'capability'

    def __init__(self, parser: 'Parser', scope: 'Scope', error: 'Error') -> None:
        Section.__init__(self, parser, scope, error)

    def pre(self) -> bool:
        return True

    def post(self) -> bool:
        return True

    def clear(self) -> None:
        pass
