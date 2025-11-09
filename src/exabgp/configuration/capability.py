
"""capability.py

Created by Thomas Mangin on 2015-06-04.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from exabgp.bgp.message.open.capability.graceful import Graceful

from exabgp.configuration.core import Section
from exabgp.configuration.parser import boolean
from exabgp.configuration.parser import string


def addpath(tokeniser):
    if not tokeniser.tokens:
        raise ValueError('add-path must be one of send, receive, send/receive, disable')

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
        raise ValueError('the option is send/receive')

    raise ValueError('"{}" is an invalid add-path, options are: send, receive, send/receive'.format(ap))


def gracefulrestart(tokeniser, default):
    if len(tokeniser.tokens) == 1:
        return default

    state = string(tokeniser)

    if state in ('disable', 'disabled'):
        return False

    try:
        grace = int(state)
    except ValueError:
        raise ValueError('"{}" is an invalid graceful-restart time'.format(state)) from None

    if grace < 0:
        raise ValueError('graceful-restart can not be negative')
    if grace > Graceful.MAX:
        raise ValueError('graceful-restart must be smaller or equal to %d' % Graceful.MAX)

    return grace


class ParseCapability(Section):
    TTL_SECURITY = 255

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

    action = {
        'nexthop': 'set-command',
        'add-path': 'set-command',
        'asn4': 'set-command',
        'graceful-restart': 'set-command',
        'multi-session': 'set-command',
        'operational': 'set-command',
        'route-refresh': 'set-command',
        'aigp': 'set-command',
        'extended-message': 'set-command',
        'software-version': 'set-command',
    }

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

    def __init__(self, tokeniser, scope, error):
        Section.__init__(self, tokeniser, scope, error)

    def pre(self):
        return True

    def post(self):
        return True

    def clear(self):
        pass
