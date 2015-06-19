# encoding: utf-8
"""
parse_capability.py

Created by Thomas Mangin on 2015-06-04.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

from exabgp.bgp.message.open.capability.graceful import Graceful

from exabgp.configuration.current.generic import Generic
from exabgp.configuration.current.generic.parser import boolean
from exabgp.configuration.current.generic.parser import string


def addpath (tokeniser):
	if not tokeniser.tokens:
		raise ValueError('add-path must be one of send, receive, send/receive, disable')

	ap = string(tokeniser).lower()

	match = {
		'disable':      0,
		'disabled':     0,
		'receive':      1,
		'send':         2,
		'send/receive': 3,
	}

	if ap in match:
		return match[ap]

	if ap == 'receive/send':  # was allowed with the previous parser
		raise ValueError('the option is send/receive')

	raise ValueError('"%s" is an invalid add-path' % ap)


def gracefulrestart (tokeniser, default):
	if not tokeniser.tokens:
		return default

	state = string(tokeniser)

	if state in ('disable','disabled'):
		return False

	try:
		grace = int(state)
	except ValueError:
		raise ValueError('"%s" is an invalid graceful-restart time' % state)

	if grace < 0:
		raise ValueError('graceful-restart can not be negative')
	if grace > Graceful.MAX:
		raise ValueError('graceful-restart must be smaller or equal to %d' % Graceful.MAX)

	return grace


class ParseCapability (Generic):
	TTL_SECURITY = 255

	syntax = \
		'syntax:\n' \
		'capability {\n' \
		'   add-path disable|send|receive|send/receive;\n' \
		'   asn4 enable|disable;\n' \
		'   graceful-restart <time in second>;\n' \
		'   multi-session enable|disable;\n' \
		'   operational enable|disable;\n' \
		'   refresh enable|disable;\n' \
		'}\n'

	known = {
		'add-path':         addpath,
		'asn4':             boolean,
		'graceful-restart': gracefulrestart,
		'multi-session':    boolean,
		'operational':      boolean,
		'route-refresh':    boolean,
	}

	action = {
		'add-path':         ['set'],
		'asn4':             ['set'],
		'graceful-restart': ['set'],
		'multi-session':    ['set'],
		'operational':      ['set'],
		'route-refresh':    ['set'],
	}

	default = {
		'asn4':             True,
		'graceful-restart': False,
		'multi-session':    False,
		'operational':      False,
		'route-refresh':    False,
	}

	name = 'capability'

	def __init__ (self, tokeniser, scope, error, logger):
		Generic.__init__(self,tokeniser,scope,error,logger)

	def clear (self):
		pass
