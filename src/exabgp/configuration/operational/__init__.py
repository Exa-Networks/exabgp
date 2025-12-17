"""operational/__init__.py

Created by Thomas Mangin on 2015-06-05.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from exabgp.configuration.core import Section
from exabgp.configuration.schema import ActionKey, ActionOperation, ActionTarget, Container, Leaf, ValueType
from exabgp.configuration.validator import LegacyParserValidator

from exabgp.configuration.operational.parser import asm
from exabgp.configuration.operational.parser import adm
from exabgp.configuration.operational.parser import rpcq
from exabgp.configuration.operational.parser import rpcp
from exabgp.configuration.operational.parser import apcq
from exabgp.configuration.operational.parser import apcp
from exabgp.configuration.operational.parser import lpcq
from exabgp.configuration.operational.parser import lpcp


class ParseOperational(Section):
    # Schema definition for operational messages
    # Validators wrap existing parser functions to maintain backward compatibility
    schema = Container(
        description='Operational messages configuration',
        children={
            'asm': Leaf(
                type=ValueType.STRING,
                description='Advisory State Message',
                target=ActionTarget.SCOPE,
                operation=ActionOperation.APPEND,
                key=ActionKey.NAME,
                validator=LegacyParserValidator(parser_func=asm, name='asm'),
            ),
            'adm': Leaf(
                type=ValueType.STRING,
                description='Advisory Dump Message',
                target=ActionTarget.SCOPE,
                operation=ActionOperation.APPEND,
                key=ActionKey.NAME,
                validator=LegacyParserValidator(parser_func=adm, name='adm'),
            ),
            'rpcq': Leaf(
                type=ValueType.STRING,
                description='Reachable Prefix Count Query',
                target=ActionTarget.SCOPE,
                operation=ActionOperation.APPEND,
                key=ActionKey.NAME,
                validator=LegacyParserValidator(parser_func=rpcq, name='rpcq'),
            ),
            'rpcp': Leaf(
                type=ValueType.STRING,
                description='Reachable Prefix Count Reply',
                target=ActionTarget.SCOPE,
                operation=ActionOperation.APPEND,
                key=ActionKey.NAME,
                validator=LegacyParserValidator(parser_func=rpcp, name='rpcp'),
            ),
            'apcq': Leaf(
                type=ValueType.STRING,
                description='Adj-RIB-Out Prefix Count Query',
                target=ActionTarget.SCOPE,
                operation=ActionOperation.APPEND,
                key=ActionKey.NAME,
                validator=LegacyParserValidator(parser_func=apcq, name='apcq'),
            ),
            'apcp': Leaf(
                type=ValueType.STRING,
                description='Adj-RIB-Out Prefix Count Reply',
                target=ActionTarget.SCOPE,
                operation=ActionOperation.APPEND,
                key=ActionKey.NAME,
                validator=LegacyParserValidator(parser_func=apcp, name='apcp'),
            ),
            'lpcq': Leaf(
                type=ValueType.STRING,
                description='Local Prefix Count Query',
                target=ActionTarget.SCOPE,
                operation=ActionOperation.APPEND,
                key=ActionKey.NAME,
                validator=LegacyParserValidator(parser_func=lpcq, name='lpcq'),
            ),
            'lpcp': Leaf(
                type=ValueType.STRING,
                description='Local Prefix Count Reply',
                target=ActionTarget.SCOPE,
                operation=ActionOperation.APPEND,
                key=ActionKey.NAME,
                validator=LegacyParserValidator(parser_func=lpcp, name='lpcp'),
            ),
        },
    )
    syntax = 'syntax:\n'

    # Empty - all entries handled by schema validators
    known: dict[str, object] = {}
    # action dict removed - derived from schema

    name = 'operational'

    def __init__(self, parser, scope, error):
        Section.__init__(self, parser, scope, error)

    def clear(self):
        pass

    def pre(self):
        self.scope.to_context()
        return True

    def post(self):
        routes = self.scope.pop(self.name)
        if routes:
            self.scope.set_value('routes', routes)
        return True
