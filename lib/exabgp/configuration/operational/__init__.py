# encoding: utf-8
"""
operational/__init__.py

Created by Thomas Mangin on 2015-06-05.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from exabgp.configuration.core import Section

from exabgp.configuration.operational.parser import asm
from exabgp.configuration.operational.parser import adm
from exabgp.configuration.operational.parser import rpcq
from exabgp.configuration.operational.parser import rpcp
from exabgp.configuration.operational.parser import apcq
from exabgp.configuration.operational.parser import apcp
from exabgp.configuration.operational.parser import lpcq
from exabgp.configuration.operational.parser import lpcp


class ParseOperational(Section):
    syntax = 'syntax:\n' ''

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

    def __init__(self, tokeniser, scope, error, logger):
        Section.__init__(self, tokeniser, scope, error, logger)

    def clear(self):
        pass

    def pre(self):
        self.scope.to_context()
        return True

    def post(self):
        routes = self.scope.pop(self.name)
        if routes:
            self.scope.set('routes', routes)
        return True
