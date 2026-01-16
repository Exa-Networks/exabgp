"""tcpao.py

TCP-AO (RFC 5925) configuration section parser.

Created by Thomas Mangin on 2025-01-15.
Copyright (c) 2009-2025 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from exabgp.configuration.core.error import Error
    from exabgp.configuration.core.parser import Parser
    from exabgp.configuration.core.scope import Scope

from exabgp.configuration.core import Section
from exabgp.configuration.schema import ActionKey, ActionOperation, ActionTarget, Container, Leaf, ValueType
from exabgp.configuration.validator import IntValidators


class ParseTCPAO(Section):
    """Parser for tcp-ao {} configuration section.

    Syntax:
        tcp-ao {
            keyid <0-255>;
            algorithm hmac-sha-1-96|aes-128-cmac-96|hmac-sha-256;
            password <string>;
            base64 true|false;
        }
    """

    schema = Container(
        description='TCP-AO (RFC 5925) authentication configuration',
        children={
            'keyid': Leaf(
                type=ValueType.INTEGER,
                description='Key ID (0-255, used for both send and receive)',
                mandatory=True,
                validator=IntValidators.range(0, 255),
                target=ActionTarget.SCOPE,
                operation=ActionOperation.SET,
                key=ActionKey.COMMAND,
            ),
            'algorithm': Leaf(
                type=ValueType.ENUMERATION,
                description='Cryptographic algorithm',
                mandatory=True,
                choices=['hmac-sha-1-96', 'aes-128-cmac-96', 'hmac-sha-256'],
                target=ActionTarget.SCOPE,
                operation=ActionOperation.SET,
                key=ActionKey.COMMAND,
            ),
            'password': Leaf(
                type=ValueType.STRING,
                description='Authentication key (max 80 bytes)',
                mandatory=True,
                target=ActionTarget.SCOPE,
                operation=ActionOperation.SET,
                key=ActionKey.COMMAND,
            ),
            'base64': Leaf(
                type=ValueType.BOOLEAN,
                description='Password is base64 encoded',
                default=False,
                target=ActionTarget.SCOPE,
                operation=ActionOperation.SET,
                key=ActionKey.COMMAND,
            ),
        },
    )

    syntax = (
        'tcp-ao {\n'
        '   keyid <0-255>;\n'
        '   algorithm hmac-sha-1-96|aes-128-cmac-96|hmac-sha-256;\n'
        '   password <string>;\n'
        '   base64 true|false;\n'
        '}\n'
    )

    known: dict[str | tuple[Any, ...], Any] = {}

    default = {
        'base64': False,
    }

    name = 'tcp-ao'

    def __init__(self, parser: 'Parser', scope: 'Scope', error: 'Error') -> None:
        Section.__init__(self, parser, scope, error)

    def pre(self) -> bool:
        return True

    def post(self) -> bool:
        return True

    def clear(self) -> None:
        pass
