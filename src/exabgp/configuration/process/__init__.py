"""parse_process.py

Created by Thomas Mangin on 2015-06-05.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import os
import sys
import uuid

from typing import TYPE_CHECKING

from exabgp.configuration.core import Section
from exabgp.configuration.schema import ActionKey, ActionOperation, ActionTarget, Container, Leaf, ValueType

from exabgp.configuration.process.parser import run

if TYPE_CHECKING:
    from exabgp.configuration.core.error import Error
    from exabgp.configuration.core.parser import Parser
    from exabgp.configuration.core.scope import Scope

API_PREFIX = 'api-internal-cli'


class ParseProcess(Section):
    # Schema definition for external process configuration
    schema = Container(
        description='External process configuration',
        children={
            'run': Leaf(
                type=ValueType.STRING,
                description='Command to execute (path and arguments)',
                mandatory=True,
                target=ActionTarget.SCOPE,
                operation=ActionOperation.SET,
                key=ActionKey.COMMAND,
            ),
            'encoder': Leaf(
                type=ValueType.ENUMERATION,
                description='Message encoding format',
                choices=['text', 'json'],
                default='text',
                target=ActionTarget.SCOPE,
                operation=ActionOperation.SET,
                key=ActionKey.COMMAND,
            ),
            'respawn': Leaf(
                type=ValueType.BOOLEAN,
                description='Restart process if it exits',
                default=True,
                target=ActionTarget.SCOPE,
                operation=ActionOperation.SET,
                key=ActionKey.COMMAND,
            ),
        },
    )

    syntax = 'process name-of-process {\n   run /path/to/command with its args;\n   encoder text|json;\n}'
    # run must stay in known - it returns list[str] and does file validation
    known = {
        'run': run,
    }
    # action dict removed - schema provides action enums

    default = {
        'respawn': True,
    }

    name = 'process'

    def __init__(self, parser: 'Parser', scope: 'Scope', error: 'Error') -> None:
        Section.__init__(self, parser, scope, error)
        self.processes: dict[str, dict[str, object]] = {}
        self._processes: list[str] = []
        self.named = ''

    def clear(self) -> None:
        self.processes = {}
        self._processes = []

    def pre(self) -> bool:
        self.named = self.parser.line[1]
        if self.named in self._processes:
            return self.error.set('a process section called "{}" already exists'.format(self.named))
        self._processes.append(self.named)
        return True

    def post(self) -> bool:
        configured = self.scope.get().keys()
        # Apply defaults from self.default dict
        for default in self.default:
            if default not in configured and isinstance(default, str):
                self.scope.set_value(default, self.default[default])
        # Apply defaults from schema
        if self.schema:
            from exabgp.configuration.schema import Leaf

            for name, child in self.schema.children.items():
                if isinstance(child, Leaf) and child.default is not None and name not in configured:
                    self.scope.set_value(name, child.default)
        # Check mandatory fields from schema
        configured = self.scope.get().keys()  # refresh after defaults
        if self.schema:
            from exabgp.configuration.schema import Leaf

            missing = []
            for name, child in self.schema.children.items():
                if isinstance(child, Leaf) and child.mandatory and name not in configured:
                    missing.append(name)
            if missing:
                return self.error.set('unset process sections: {}'.format(', '.join(missing)))
        self.processes.update({self.named: self.scope.pop()})
        return True

    def add_api(self) -> None:
        prog = os.path.join(os.environ.get('PWD', ''), sys.argv[0])

        # Add pipe-based process if enabled
        cli_pipe = os.environ.get('exabgp_cli_pipe', '')
        if cli_pipe:
            name = '{}-pipe-{:x}'.format(API_PREFIX, uuid.uuid1().fields[0])
            api = {
                name: {
                    'run': [sys.executable, prog],
                    'encoder': 'text',
                    'respawn': True,
                    'env': {
                        'exabgp_api_cli_mode': 'pipe',
                    },
                },
            }
            self._processes.append(name)
            self.processes.update(api)

        # Add socket-based process if enabled
        cli_socket = os.environ.get('exabgp_cli_socket', '')
        if cli_socket:
            name = '{}-socket-{:x}'.format(API_PREFIX, uuid.uuid1().fields[0])
            api = {
                name: {
                    'run': [sys.executable, prog],
                    'encoder': 'text',
                    'respawn': True,
                    'env': {
                        'exabgp_api_cli_mode': 'socket',
                    },
                },
            }
            self._processes.append(name)
            self.processes.update(api)
