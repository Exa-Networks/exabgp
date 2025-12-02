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
from exabgp.configuration.schema import Container, Leaf, ValueType


class _ParseDirection(Section):
    # Schema definition for send/receive direction configuration
    _direction_schema = Container(
        description='Message types to forward to external processes',
        children={
            'parsed': Leaf(
                type=ValueType.BOOLEAN,
                description='Forward parsed messages',
                default=True,
            ),
            'packets': Leaf(
                type=ValueType.BOOLEAN,
                description='Forward raw packets',
                default=True,
            ),
            'consolidate': Leaf(
                type=ValueType.BOOLEAN,
                description='Consolidate updates',
                default=True,
            ),
            'open': Leaf(
                type=ValueType.BOOLEAN,
                description='Forward OPEN messages',
                default=True,
            ),
            'update': Leaf(
                type=ValueType.BOOLEAN,
                description='Forward UPDATE messages',
                default=True,
            ),
            'notification': Leaf(
                type=ValueType.BOOLEAN,
                description='Forward NOTIFICATION messages',
                default=True,
            ),
            'keepalive': Leaf(
                type=ValueType.BOOLEAN,
                description='Forward KEEPALIVE messages',
                default=True,
            ),
            'refresh': Leaf(
                type=ValueType.BOOLEAN,
                description='Forward ROUTE-REFRESH messages',
                default=True,
            ),
            'operational': Leaf(
                type=ValueType.BOOLEAN,
                description='Forward OPERATIONAL messages',
                default=True,
            ),
        },
    )
    action = {
        'parsed': 'set-command',
        'packets': 'set-command',
        'consolidate': 'set-command',
        'open': 'set-command',
        'update': 'set-command',
        'notification': 'set-command',
        'keepalive': 'set-command',
        'refresh': 'set-command',
        'operational': 'set-command',
    }

    known = {
        'parsed': boolean,
        'packets': boolean,
        'consolidate': boolean,
        'open': boolean,
        'update': boolean,
        'notification': boolean,
        'keepalive': boolean,
        'refresh': boolean,
        'operational': boolean,
    }

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

    syntax = '{{\n  {};\n}}'.format(';\n  '.join(default.keys()))  # type: ignore[arg-type]

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
            ),
            'processes-match': Leaf(
                type=ValueType.STRING,
                description='Regex pattern to match process names',
            ),
            'neighbor-changes': Leaf(
                type=ValueType.BOOLEAN,
                description='Notify on neighbor state changes',
                default=True,
            ),
            'negotiated': Leaf(
                type=ValueType.BOOLEAN,
                description='Notify on negotiation completion',
                default=True,
            ),
            'fsm': Leaf(
                type=ValueType.BOOLEAN,
                description='Notify on FSM state changes',
                default=True,
            ),
            'signal': Leaf(
                type=ValueType.BOOLEAN,
                description='Notify on signals',
                default=True,
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

    action = {
        'processes': 'set-command',
        'processes-match': 'set-command',
        'neighbor-changes': 'set-command',
        'negotiated': 'set-command',
        'fsm': 'set-command',
        'signal': 'set-command',
    }

    default = {
        'neighbor-changes': True,
        'negotiated': True,
        'fsm': True,
        'signal': True,
    }

    DEFAULT_API: dict[str, list] = {
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
