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

from exabgp.configuration.core import Section
from exabgp.configuration.parser import string
from exabgp.configuration.schema import ActionKey, ActionOperation, ActionTarget, Container, Leaf, ValueType
from exabgp.configuration.validator import IntValidators


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
                target=ActionTarget.SCOPE,
                operation=ActionOperation.SET,
                key=ActionKey.COMMAND,
            ),
            'add-path': Leaf(
                type=ValueType.ENUMERATION,
                description='ADD-PATH capability mode',
                choices=['disable', 'receive', 'send', 'send/receive'],
                target=ActionTarget.SCOPE,
                operation=ActionOperation.SET,
                key=ActionKey.COMMAND,
            ),
            'asn4': Leaf(
                type=ValueType.BOOLEAN,
                description='4-byte AS number capability',
                default=True,
                target=ActionTarget.SCOPE,
                operation=ActionOperation.SET,
                key=ActionKey.COMMAND,
            ),
            'graceful-restart': Leaf(
                type=ValueType.INTEGER,
                description='Graceful restart time in seconds (0 to use hold-time, or "disable")',
                default=0,
                validator=IntValidators.graceful_restart(),
                target=ActionTarget.SCOPE,
                operation=ActionOperation.SET,
                key=ActionKey.COMMAND,
            ),
            'multi-session': Leaf(
                type=ValueType.BOOLEAN,
                description='Multi-session capability',
                default=True,
                target=ActionTarget.SCOPE,
                operation=ActionOperation.SET,
                key=ActionKey.COMMAND,
            ),
            'operational': Leaf(
                type=ValueType.BOOLEAN,
                description='Operational capability for advisory messages',
                default=True,
                target=ActionTarget.SCOPE,
                operation=ActionOperation.SET,
                key=ActionKey.COMMAND,
            ),
            'route-refresh': Leaf(
                type=ValueType.BOOLEAN,
                description='Route refresh capability',
                default=True,
                target=ActionTarget.SCOPE,
                operation=ActionOperation.SET,
                key=ActionKey.COMMAND,
            ),
            'aigp': Leaf(
                type=ValueType.BOOLEAN,
                description='AIGP (Accumulated IGP Metric) capability',
                default=True,
                target=ActionTarget.SCOPE,
                operation=ActionOperation.SET,
                key=ActionKey.COMMAND,
            ),
            'extended-message': Leaf(
                type=ValueType.BOOLEAN,
                description='Extended message capability (>4096 bytes)',
                default=True,
                target=ActionTarget.SCOPE,
                operation=ActionOperation.SET,
                key=ActionKey.COMMAND,
            ),
            'software-version': Leaf(
                type=ValueType.BOOLEAN,
                description='Software version capability',
                default=False,
                target=ActionTarget.SCOPE,
                operation=ActionOperation.SET,
                key=ActionKey.COMMAND,
            ),
            'link-local-nexthop': Leaf(
                type=ValueType.BOOLEAN,
                description='Link-local next-hop capability (RFC draft-ietf-idr-linklocal-capability)',
                default=None,
                target=ActionTarget.SCOPE,
                operation=ActionOperation.SET,
                key=ActionKey.COMMAND,
            ),
            'link-local-prefer': Leaf(
                type=ValueType.BOOLEAN,
                description='Prefer link-local over global IPv6 next-hop when both present',
                default=False,
                target=ActionTarget.SCOPE,
                operation=ActionOperation.SET,
                key=ActionKey.COMMAND,
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
        '   link-local-nexthop enable|disable;\n'
        '   link-local-prefer enable|disable;\n'
        '}\n'
    )

    # Schema validators handle BOOLEAN entries and graceful-restart.
    # Only entries with special parsing logic remain in known:
    known = {
        'add-path': addpath,  # Returns int (0,1,2,3), not string
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
        'link-local-nexthop': None,
        'link-local-prefer': False,
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
