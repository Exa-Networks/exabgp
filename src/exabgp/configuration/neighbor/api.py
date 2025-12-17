"""parse_process.py

Created by Thomas Mangin on 2015-06-05.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import time
import copy
from typing import Any

from exabgp.configuration.core import Section
from exabgp.configuration.core import Parser
from exabgp.configuration.core import Scope
from exabgp.configuration.core import Error
from exabgp.configuration.parser import boolean
from exabgp.configuration.neighbor.parser import processes
from exabgp.configuration.neighbor.parser import processes_match
from exabgp.configuration.schema import ActionKey, ActionOperation, ActionTarget, Container, Leaf, ValueType


# ParseSend and ParseReceive use schema validators for boolean fields
# (parsed, packets, consolidate, open, update, notification, keepalive, refresh, operational)


class _ParseDirection(Section):
    # Schema definition for send/receive direction configuration
    # All boolean fields use schema validators (no known dict entries needed)
    _direction_schema = Container(
        description='Message types to forward to external processes',
        children={
            'parsed': Leaf(
                type=ValueType.BOOLEAN,
                description='Forward parsed messages',
                default=True,
                target=ActionTarget.SCOPE,
                operation=ActionOperation.SET,
                key=ActionKey.COMMAND,
            ),
            'packets': Leaf(
                type=ValueType.BOOLEAN,
                description='Forward raw packets',
                default=True,
                target=ActionTarget.SCOPE,
                operation=ActionOperation.SET,
                key=ActionKey.COMMAND,
            ),
            'consolidate': Leaf(
                type=ValueType.BOOLEAN,
                description='Consolidate updates',
                default=True,
                target=ActionTarget.SCOPE,
                operation=ActionOperation.SET,
                key=ActionKey.COMMAND,
            ),
            'open': Leaf(
                type=ValueType.BOOLEAN,
                description='Forward OPEN messages',
                default=True,
                target=ActionTarget.SCOPE,
                operation=ActionOperation.SET,
                key=ActionKey.COMMAND,
            ),
            'update': Leaf(
                type=ValueType.BOOLEAN,
                description='Forward UPDATE messages',
                default=True,
                target=ActionTarget.SCOPE,
                operation=ActionOperation.SET,
                key=ActionKey.COMMAND,
            ),
            'notification': Leaf(
                type=ValueType.BOOLEAN,
                description='Forward NOTIFICATION messages',
                default=True,
                target=ActionTarget.SCOPE,
                operation=ActionOperation.SET,
                key=ActionKey.COMMAND,
            ),
            'keepalive': Leaf(
                type=ValueType.BOOLEAN,
                description='Forward KEEPALIVE messages',
                default=True,
                target=ActionTarget.SCOPE,
                operation=ActionOperation.SET,
                key=ActionKey.COMMAND,
            ),
            'refresh': Leaf(
                type=ValueType.BOOLEAN,
                description='Forward ROUTE-REFRESH messages',
                default=True,
                target=ActionTarget.SCOPE,
                operation=ActionOperation.SET,
                key=ActionKey.COMMAND,
            ),
            'operational': Leaf(
                type=ValueType.BOOLEAN,
                description='Forward OPERATIONAL messages',
                default=True,
                target=ActionTarget.SCOPE,
                operation=ActionOperation.SET,
                key=ActionKey.COMMAND,
            ),
        },
    )
    # Empty - all handled by schema validators
    known: dict[str, object] = {}
    action: dict[str, object] = {}

    default = {
        'parsed': True,
        'packets': True,
        'consolidate': True,
        'open': True,
        'update': True,
        'notification': True,
        'keepalive': True,
        'refresh': True,
        'operational': True,
    }

    syntax = '{{\n  {};\n}}'.format(';\n  '.join(default.keys()))

    def __init__(self, parser: Parser, scope: Scope, error: Error) -> None:
        Section.__init__(self, parser, scope, error)

    def clear(self) -> None:
        pass

    def pre(self) -> bool:
        return True

    def post(self) -> bool:
        return True


class ParseSend(_ParseDirection):
    schema = _ParseDirection._direction_schema
    syntax = 'send {}'.format(_ParseDirection.syntax)

    name = 'api/send'


class ParseReceive(_ParseDirection):
    schema = _ParseDirection._direction_schema
    syntax = 'receive {}'.format(_ParseDirection.syntax)

    name = 'api/receive'


class ParseAPI(Section):
    # Schema definition for API configuration
    schema = Container(
        description='API configuration for external process communication',
        children={
            'processes': Leaf(
                type=ValueType.STRING,
                description='List of process names to communicate with',
                target=ActionTarget.SCOPE,
                operation=ActionOperation.EXTEND,
                key=ActionKey.COMMAND,
            ),
            'processes-match': Leaf(
                type=ValueType.STRING,
                description='Regex pattern to match process names',
                target=ActionTarget.SCOPE,
                operation=ActionOperation.EXTEND,
                key=ActionKey.COMMAND,
            ),
            'neighbor-changes': Leaf(
                type=ValueType.BOOLEAN,
                description='Notify on neighbor state changes',
                default=True,
                target=ActionTarget.SCOPE,
                operation=ActionOperation.SET,
                key=ActionKey.COMMAND,
            ),
            'negotiated': Leaf(
                type=ValueType.BOOLEAN,
                description='Notify on negotiation completion',
                default=True,
                target=ActionTarget.SCOPE,
                operation=ActionOperation.SET,
                key=ActionKey.COMMAND,
            ),
            'fsm': Leaf(
                type=ValueType.BOOLEAN,
                description='Notify on FSM state changes',
                default=True,
                target=ActionTarget.SCOPE,
                operation=ActionOperation.SET,
                key=ActionKey.COMMAND,
            ),
            'signal': Leaf(
                type=ValueType.BOOLEAN,
                description='Notify on signals',
                default=True,
                target=ActionTarget.SCOPE,
                operation=ActionOperation.SET,
                key=ActionKey.COMMAND,
            ),
            'send': Container(description='Messages to send to processes'),
            'receive': Container(description='Messages to receive from processes'),
        },
    )

    syntax = (
        'process {{\n'
        '  processes [ name-of-processes ];\n'
        '  processes-match [ regex-of-processes ];\n'
        '  neighbor-changes;\n'
        '  {}\n'
        '  {}\n'
        '}}'.format('\n  '.join(ParseSend.syntax.split('\n')), '\n  '.join(ParseReceive.syntax.split('\n')))
    )

    known = {
        'processes': processes,
        'processes-match': processes_match,
        'neighbor-changes': boolean,
        'negotiated': boolean,
        'fsm': boolean,
        'signal': boolean,
    }
    # action dict removed - schema provides action enums (SET is default for Leaf)

    default = {
        'neighbor-changes': True,
        'negotiated': True,
        'fsm': True,
        'signal': True,
    }

    DEFAULT_API: dict[str, list[str]] = {
        'neighbor-changes': [],
        'negotiated': [],
        'fsm': [],
        'signal': [],
        'processes': [],
        'processes-match': [],
    }

    name = 'api'

    def __init__(self, parser: Parser, scope: Scope, error: Error) -> None:
        Section.__init__(self, parser, scope, error)
        self.api: dict[str, Any] = {}
        self.named: str = ''

    @classmethod
    def _empty(cls) -> dict[str, Any]:
        return copy.deepcopy(cls.DEFAULT_API)

    def clear(self) -> None:
        self.api = {}
        self.named = ''
        Section.clear(self)

    def pre(self) -> bool:
        named = self.parser.tokeniser()
        self.named = named if named else 'auto-named-%d' % int(time.time() * 1000000)
        self.check_name(self.named)
        self.scope.enter(self.named)
        self.scope.to_context()
        return True

    def post(self) -> bool:
        self.scope.leave()
        self.scope.to_context()
        return True

    @classmethod
    def flatten(cls, apis: dict[str, Any]) -> dict[str, Any]:
        built = cls._empty()

        for api in apis.values():
            procs = api.get('processes', [])
            mprocs = api.get('processes-match', [])

            built.setdefault('processes', []).extend(procs)
            built.setdefault('processes-match', []).extend(mprocs)

            for command in ('neighbor-changes', 'negotiated', 'fsm', 'signal'):
                built.setdefault(command, []).extend(procs if api.get(command, False) else [])

            for direction in ('send', 'receive'):
                data = api.get(direction, {})
                for action in (
                    'parsed',
                    'packets',
                    'consolidate',
                    'open',
                    'update',
                    'notification',
                    'keepalive',
                    'refresh',
                    'operational',
                ):
                    built.setdefault('{}-{}'.format(direction, action), []).extend(
                        procs if data.get(action, False) else []
                    )

        return built


for way in ('send', 'receive'):
    for name in (
        'parsed',
        'packets',
        'consolidate',
        'open',
        'update',
        'notification',
        'keepalive',
        'refresh',
        'operational',
    ):
        ParseAPI.DEFAULT_API['{}-{}'.format(way, name)] = []
