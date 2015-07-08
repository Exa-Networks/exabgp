# encoding: utf-8
"""
parse_capability.py

Created by Thomas Mangin on 2015-06-04.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

from exabgp.bgp.message.open.capability.graceful import Graceful

from exabgp.configuration.core import Section
from exabgp.configuration.parser import boolean
from exabgp.configuration.parser import string


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

	raise ValueError('"%s" is an invalid add-path, options are send, receive, send/receive' % ap)


def gracefulrestart (tokeniser, default):
	if len(tokeniser.tokens) == 1:
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


class ParseCapability (Section):
	TTL_SECURITY = 255

	syntax = \
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
		'aigp':             boolean,
	}

	action = {
		'add-path':         'set-command',
		'asn4':             'set-command',
		'graceful-restart': 'set-command',
		'multi-session':    'set-command',
		'operational':      'set-command',
		'route-refresh':    'set-command',
		'aigp':             'set-command',
	}

	default = {
		'asn4':             True,
		'graceful-restart': 0,
		'multi-session':    True,
		'operational':      True,
		'route-refresh':    True,
		'aigp':             True,
	}

	name = 'capability'

	def __init__ (self, tokeniser, scope, error, logger):
		Section.__init__(self,tokeniser,scope,error,logger)

	def pre (self):
		self.scope.to_context()
		return True

	def post (self):
		return True

	def clear (self):
		pass
