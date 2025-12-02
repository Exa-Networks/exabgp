"""operational/__init__.py

Created by Thomas Mangin on 2015-06-05.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from exabgp.configuration.core import Section
from exabgp.configuration.schema import Container, Leaf, ValueType

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
    schema = Container(
        description='Operational messages configuration',
        children={
            'asm': Leaf(
                type=ValueType.STRING,
                description='Advisory State Message',
                action='append-name',
            ),
            'adm': Leaf(
                type=ValueType.STRING,
                description='Advisory Dump Message',
                action='append-name',
            ),
            'rpcq': Leaf(
                type=ValueType.STRING,
                description='Reachable Prefix Count Query',
                action='append-name',
            ),
            'rpcp': Leaf(
                type=ValueType.STRING,
                description='Reachable Prefix Count Reply',
                action='append-name',
            ),
            'apcq': Leaf(
                type=ValueType.STRING,
                description='Adj-RIB-Out Prefix Count Query',
                action='append-name',
            ),
            'apcp': Leaf(
                type=ValueType.STRING,
                description='Adj-RIB-Out Prefix Count Reply',
                action='append-name',
            ),
            'lpcq': Leaf(
                type=ValueType.STRING,
                description='Local Prefix Count Query',
                action='append-name',
            ),
            'lpcp': Leaf(
                type=ValueType.STRING,
                description='Local Prefix Count Reply',
                action='append-name',
            ),
        },
    )
    syntax = 'syntax:\n'

    known = {
        'asm': asm,
        'adm': adm,
        'rpcq': rpcq,
        'rpcp': rpcp,
        'apcq': apcq,
        'apcp': apcp,
        'lpcq': lpcq,
        'lpcp': lpcp,
    }

    action = {
        'asm': 'append-name',
        'adm': 'append-name',
        'rpcq': 'append-name',
        'rpcp': 'append-name',
        'apcq': 'append-name',
        'apcp': 'append-name',
        'lpcq': 'append-name',
        'lpcp': 'append-name',
    }

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
