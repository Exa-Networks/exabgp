# encoding: utf-8
"""
parse_process.py

Created by Thomas Mangin on 2015-06-05.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

import time
import copy
from collections import defaultdict

from exabgp.configuration.core import Section
from exabgp.configuration.parser import boolean
from exabgp.configuration.neighbor.parser import processes


class _ParseDirection(Section):
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

    syntax = '{\n  %s;\n}' % ';\n  '.join(default.keys())

    def __init__(self, tokeniser, scope, error, logger):
        Section.__init__(self, tokeniser, scope, error, logger)

    def clear(self):
        pass

    def pre(self):
        return True

    def post(self):
        return True


class ParseSend(_ParseDirection):
    syntax = 'send %s' % _ParseDirection.syntax

    name = 'api/send'


class ParseReceive(_ParseDirection):
    syntax = 'receive %s' % _ParseDirection.syntax

    name = 'api/receive'


class ParseAPI(Section):
    syntax = (
        'process {\n'
        '  processes [ name-of-processes ];\n'
        '  neighbor-changes;\n'
        '  %s\n'
        '  %s\n'
        '}' % ('\n  '.join(ParseSend.syntax.split('\n')), '\n  '.join(ParseReceive.syntax.split('\n')))
    )

    known = {
        'processes': processes,
        'neighbor-changes': boolean,
        'negotiated': boolean,
        'fsm': boolean,
        'signal': boolean,
    }

    action = {
        'processes': 'set-command',
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

    DEFAULT_API = {
        'neighbor-changes': [],
        'negotiated': [],
        'fsm': [],
        'signal': [],
        'processes': [],
    }

    name = 'api'

    def __init__(self, tokeniser, scope, error, logger):
        Section.__init__(self, tokeniser, scope, error, logger)
        self.api = {}
        self.named = ''

    @classmethod
    def _empty(cls):
        return copy.deepcopy(cls.DEFAULT_API)

    def clear(self):
        self.api = {}
        self.named = ''
        Section.clear(self)

    def pre(self):
        named = self.tokeniser.iterate()
        self.named = named if named else 'auto-named-%d' % int(time.time() * 1000000)
        self.check_name(self.named)
        self.scope.enter(self.named)
        self.scope.to_context()
        return True

    def post(self):
        self.scope.leave()
        self.scope.to_context()
        return True

    @classmethod
    def flatten(cls, apis):
        built = cls._empty()

        for api in apis.values():
            procs = api.get('processes', [])

            built.setdefault('processes', []).extend(procs)

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
                    built.setdefault("%s-%s" % (direction, action), []).extend(procs if data.get(action, False) else [])

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
        ParseAPI.DEFAULT_API["%s-%s" % (way, name)] = []
